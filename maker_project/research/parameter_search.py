"""AS parameter optimization and robust validation workflow."""

from __future__ import annotations

import hashlib
import json
import math
import random
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd

from ..backtest.batch_runner import run_single_day
from ..backtest.data_loader import load_processed_data_for_date
from ..backtest.engine import BacktestEngine
from ..backtest.summary import summarize_results, save_summary
from ..configs.default_config import (
    DEFAULT_ALPHA_WEIGHT,
    DEFAULT_BASE_SPREAD,
    DEFAULT_DATA_DIR,
    DEFAULT_END_DATE,
    DEFAULT_GAMMA,
    DEFAULT_IMBALANCE_WEIGHT,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_INV_WEIGHT,
    DEFAULT_MAX_POSITION,
    DEFAULT_MAX_SPREAD,
    DEFAULT_MIN_SPREAD,
    DEFAULT_ORDER_SIZE,
    DEFAULT_REBATE_BPS,
    DEFAULT_RESULTS_DIR,
    DEFAULT_SAMPLE_N,
    DEFAULT_SHORT_RETURN_WINDOW,
    DEFAULT_START_DATE,
    DEFAULT_TICK_SIZE,
    DEFAULT_VOL_WEIGHT,
    DEFAULT_VOL_WINDOW,
)
from ..strategies import (
    ASMarketMakingStrategy,
    ASOptimizedMarketMakingStrategy,
    InventoryAwareMakerStrategy,
    SimpleMakerStrategy,
)

DEFAULT_AS_PARAM_GRID: Dict[str, List[Any]] = {
    "gamma": [0.05, 0.1, 0.2, 0.4],
    "base_spread": [0.1, 0.2, 0.3, 0.5],
    "vol_weight": [0.5, 1.0, 1.5, 2.0],
    "inv_weight": [0.5, 1.0, 1.5, 2.0],
    "alpha_weight": [0.0, 0.5, 1.0, 2.0],
    "imbalance_weight": [0.0, 0.5, 1.0, 2.0],
    "min_spread": [0.1, 0.2, 0.3],
    "short_return_window": [10, 30, 50, 100],
    "vol_window": [50, 100, 200],
}


def _normalize_dates(dates: Sequence[str] | str) -> List[str]:
    if isinstance(dates, str):
        return [dates]
    return list(dates)


def _results_root(base_config: Dict[str, Any]) -> Path:
    return Path(base_config.get("results_dir", DEFAULT_RESULTS_DIR))


def _optimization_root(base_config: Dict[str, Any]) -> Path:
    return _results_root(base_config) / "optimization"


def _build_strategy(params: Dict[str, Any]) -> ASOptimizedMarketMakingStrategy:
    return ASOptimizedMarketMakingStrategy(
        order_size=params.get("order_size", DEFAULT_ORDER_SIZE),
        max_spread=params.get("max_spread", DEFAULT_MAX_SPREAD),
        tick_size=params.get("tick_size", DEFAULT_TICK_SIZE),
        gamma=params["gamma"],
        base_spread=params["base_spread"],
        vol_weight=params["vol_weight"],
        inv_weight=params["inv_weight"],
        alpha_weight=params["alpha_weight"],
        imbalance_weight=params["imbalance_weight"],
        min_spread=params["min_spread"],
        vol_threshold=params.get("vol_threshold"),
        alpha_to_position_scale=params.get("alpha_to_position_scale", 0.2),
        size_skew=params.get("size_skew", 1.5),
    )


def _build_base_strategy(strategy_name: str, base_config: Dict[str, Any]):
    common = {
        "order_size": base_config.get("order_size", DEFAULT_ORDER_SIZE),
        "max_spread": base_config.get("max_spread", DEFAULT_MAX_SPREAD),
    }
    if strategy_name == "simple":
        return SimpleMakerStrategy(**common)
    if strategy_name == "inventory":
        return InventoryAwareMakerStrategy(**common)
    if strategy_name == "as":
        return ASMarketMakingStrategy(
            **common,
            tick_size=base_config.get("tick_size", DEFAULT_TICK_SIZE),
            gamma=base_config.get("gamma", DEFAULT_GAMMA),
            base_spread=base_config.get("base_spread", DEFAULT_BASE_SPREAD),
            vol_weight=base_config.get("vol_weight", DEFAULT_VOL_WEIGHT),
            inv_weight=base_config.get("inv_weight", DEFAULT_INV_WEIGHT),
            alpha_weight=base_config.get("alpha_weight", DEFAULT_ALPHA_WEIGHT),
            imbalance_weight=base_config.get("imbalance_weight", DEFAULT_IMBALANCE_WEIGHT),
            min_spread=base_config.get("min_spread", DEFAULT_MIN_SPREAD),
        )
    raise ValueError(f"Unsupported baseline strategy: {strategy_name}")


def _params_to_key(params: Dict[str, Any]) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()[:12]


def _objective_score(summary: Dict[str, Any]) -> float:
    mean_pnl = float(summary.get("mean_pnl", 0.0))
    mean_inventory_pnl = float(summary.get("mean_inventory_pnl", 0.0))
    mean_rebate_share = float(summary.get("mean_rebate_share", 0.0))
    mean_position = float(summary.get("mean_position", 0.0))
    mean_long_ratio = float(summary.get("mean_long_ratio", 0.0))
    mean_short_ratio = float(summary.get("mean_short_ratio", 0.0))
    worst_day_pnl = float(summary.get("worst_day_pnl", 0.0))
    sharpe_like = float(summary.get("sharpe_like", 0.0))
    win_days_ratio = float(summary.get("win_days_ratio", 0.0))

    objective_score = (
        sharpe_like
        + 0.5 * win_days_ratio
        + 0.3 * max(mean_inventory_pnl, 0)
        - 0.5 * max(mean_rebate_share - 0.8, 0)
        - 0.5 * abs(mean_position)
        - 0.3 * max(abs(mean_long_ratio - mean_short_ratio) - 0.3, 0)
        - 0.5 * max(abs(worst_day_pnl) / max(abs(mean_pnl), 1) - 3, 0)
    )
    return float(objective_score)


def _sample_param_combinations(
    param_grid: Dict[str, List[Any]],
    param_samples: int,
    random_seed: int = 42,
) -> List[Dict[str, Any]]:
    keys = list(param_grid.keys())
    all_combinations = [dict(zip(keys, values)) for values in product(*[param_grid[key] for key in keys])]

    if param_samples is None or param_samples <= 0 or param_samples >= len(all_combinations):
        return all_combinations

    rng = random.Random(random_seed)
    return rng.sample(all_combinations, k=param_samples)


def _load_existing_rows(csv_path: Path) -> pd.DataFrame:
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def _append_row(csv_path: Path, row: Dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    header = not csv_path.exists()
    df.to_csv(csv_path, mode="a", header=header, index=False)


def _train_dates_from_range(train_dates: Sequence[str] | str) -> List[str]:
    dates = _normalize_dates(train_dates)
    if len(dates) == 1 and "to" in dates[0]:
        raise ValueError("Pass explicit date list or start/end pair; use the workflow helper for ranges.")
    return dates


def _preload_daily_data(dates: Sequence[str], data_dir: str | Path) -> Dict[str, pd.DataFrame]:
    """Pre-load all daily data for a date range."""
    print(f"  Pre-loading {len(dates)} days of data...")
    data_dict = {}
    for date in dates:
        data_dict[date] = load_processed_data_for_date(data_dir, date)
    print(f"  ✓ Pre-loaded {len(data_dict)} days")
    return data_dict


def _run_daily_sequence(
    dates: Sequence[str],
    strategy,
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run daily sequence by loading data from disk (fallback)."""
    results: List[Dict[str, Any]] = []
    for date in dates:
        results.append(run_single_day(date, strategy, config))
    return results


def _run_daily_sequence_with_preloaded_data(
    dates: Sequence[str],
    strategy,
    config: Dict[str, Any],
    preloaded_data: Dict[str, pd.DataFrame],
) -> List[Dict[str, Any]]:
    """Run daily sequence using pre-loaded data (no disk reads per parameter)."""
    import copy
    from ..backtest.models import Market, Account, Order, Fill
    
    results: List[Dict[str, Any]] = []
    for date in dates:
        if date not in preloaded_data:
            raise ValueError(f"Date {date} not in preloaded data")
        
        daily_data = preloaded_data[date]
        strategy_instance = copy.deepcopy(strategy)
        
        engine = BacktestEngine(
            data=daily_data,
            strategy=strategy_instance,
            initial_capital=config.get("initial_capital", 100000),
            rebate_bps=config.get("rebate_bps", -0.5),
            fill_model=config.get("fill_model", "touch"),
            max_position=config.get("max_position", 1.0),
            sample_n=config.get("sample_n"),
            vol_window=config.get("vol_window", 50),
            short_return_window=config.get("short_return_window", 10),
        )
        results_df, metrics = engine.run()
        
        metrics["date"] = date
        results.append(metrics)
    
    return results


def run_as_parameter_search(
    train_dates: Sequence[str],
    test_dates: Sequence[str],
    param_grid: Dict[str, List[Any]],
    base_config: Dict[str, Any],
) -> pd.DataFrame:
    """Run train-only AS parameter search with resumable CSV checkpoints."""
    optimization_root = _optimization_root(base_config)
    optimization_root.mkdir(parents=True, exist_ok=True)
    train_csv_path = optimization_root / "as_param_search_train.csv"

    train_dates_list = _normalize_dates(train_dates)
    _ = _normalize_dates(test_dates)
    param_samples = int(base_config.get("param_samples", 200))
    sampled_param_sets = _sample_param_combinations(param_grid, param_samples, base_config.get("random_seed", 42))

    existing_df = _load_existing_rows(train_csv_path)
    existing_keys = set(existing_df["param_key"].astype(str)) if not existing_df.empty and "param_key" in existing_df.columns else set()

    # PRE-LOAD ALL TRAIN DATA
    print("TRAIN PHASE: Parameter Search")
    print("=" * 70)
    train_data = _preload_daily_data(train_dates_list, base_config["data_dir"])

    rows: List[Dict[str, Any]] = []
    for idx, params in enumerate(sampled_param_sets, start=1):
        row_params = dict(params)
        row_params["order_size"] = base_config.get("order_size", DEFAULT_ORDER_SIZE)
        row_params["max_spread"] = base_config.get("max_spread", DEFAULT_MAX_SPREAD)
        row_params["tick_size"] = base_config.get("tick_size", DEFAULT_TICK_SIZE)
        row_params["vol_threshold"] = base_config.get("vol_threshold")
        row_params["alpha_to_position_scale"] = base_config.get("alpha_to_position_scale", 0.2)
        row_params["size_skew"] = base_config.get("size_skew", 1.5)

        param_key = _params_to_key(row_params)
        if param_key in existing_keys:
            continue

        strategy = _build_strategy(row_params)
        run_config = dict(base_config)
        run_config.update(
            {
                "strategy_name": "as_opt",
                "run_label": f"as_opt_{param_key}",
                "save_daily": False,
            }
        )

        # USE PRE-LOADED DATA (no disk reads)
        print(f"  [{idx}/{len(sampled_param_sets)}] Evaluating {param_key}...")
        daily_results = _run_daily_sequence_with_preloaded_data(train_dates_list, strategy, run_config, train_data)
        summary = summarize_results(daily_results)
        summary["strategy"] = "as_opt"
        summary["params"] = json.dumps(row_params, sort_keys=True)
        summary["param_key"] = param_key
        summary["objective_score"] = _objective_score(summary)

        record = {
            "strategy": summary["strategy"],
            "param_key": param_key,
            "params": summary["params"],
            "train_mean_pnl": summary.get("mean_pnl", 0.0),
            "train_std_pnl": summary.get("std_pnl", 0.0),
            "train_sharpe_like": summary.get("sharpe_like", 0.0),
            "train_win_days_ratio": summary.get("win_days_ratio", 0.0),
            "train_mean_rebate_share": summary.get("mean_rebate_share", 0.0),
            "train_mean_inventory_pnl": summary.get("mean_inventory_pnl", 0.0),
            "train_mean_turnover": summary.get("mean_turnover", 0.0),
            "train_mean_position": summary.get("mean_position", 0.0),
            "train_long_ratio": summary.get("mean_long_ratio", 0.0),
            "train_short_ratio": summary.get("mean_short_ratio", 0.0),
            "train_worst_day_pnl": summary.get("worst_day_pnl", 0.0),
            "objective_score": summary["objective_score"],
            "train_total_pnl_sum": summary.get("total_pnl_sum", 0.0),
            "train_mean_drawdown": summary.get("mean_drawdown", 0.0),
            "train_tail_risk_ratio": summary.get("tail_risk_ratio", 0.0),
        }
        _append_row(train_csv_path, record)
        rows.append(record)

    if existing_df.empty:
        return pd.DataFrame(rows)

    combined_df = pd.concat([existing_df, pd.DataFrame(rows)], ignore_index=True)
    if "objective_score" in combined_df.columns:
        combined_df = combined_df.sort_values(["objective_score", "train_sharpe_like"], ascending=[False, False])
    combined_df = combined_df.drop_duplicates(subset=["param_key"], keep="first")
    combined_df.to_csv(train_csv_path, index=False)
    return combined_df


def _extract_params(params_json: str) -> Dict[str, Any]:
    params = json.loads(params_json)
    return params


def _evaluate_strategy_on_test(
    dates: Sequence[str],
    strategy,
    base_config: Dict[str, Any],
    strategy_name: str,
    preloaded_data: Dict[str, pd.DataFrame] | None = None,
) -> Dict[str, Any]:
    run_config = dict(base_config)
    run_config.update(
        {
            "strategy_name": strategy_name,
            "run_label": strategy_name,
            "save_daily": False,
        }
    )
    
    if preloaded_data is not None:
        daily_results = _run_daily_sequence_with_preloaded_data(dates, strategy, run_config, preloaded_data)
    else:
        daily_results = _run_daily_sequence(dates, strategy, run_config)
    
    summary = summarize_results(daily_results)
    summary["strategy"] = strategy_name
    return summary


def _summary_row_from_summary(summary: Dict[str, Any], label: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    row = {
        "strategy": label,
        "mean_pnl": summary.get("mean_pnl", 0.0),
        "std_pnl": summary.get("std_pnl", 0.0),
        "sharpe_like": summary.get("sharpe_like", 0.0),
        "win_days_ratio": summary.get("win_days_ratio", 0.0),
        "total_pnl_sum": summary.get("total_pnl_sum", 0.0),
        "mean_rebate_share": summary.get("mean_rebate_share", 0.0),
        "mean_inventory_pnl": summary.get("mean_inventory_pnl", 0.0),
        "mean_turnover": summary.get("mean_turnover", 0.0),
        "mean_position": summary.get("mean_position", 0.0),
        "mean_long_ratio": summary.get("mean_long_ratio", 0.0),
        "mean_short_ratio": summary.get("mean_short_ratio", 0.0),
        "worst_day_pnl": summary.get("worst_day_pnl", 0.0),
        "best_day_pnl": summary.get("best_day_pnl", 0.0),
        "tail_risk_ratio": summary.get("tail_risk_ratio", 0.0),
    }
    if params is not None:
        row["params"] = json.dumps(params, sort_keys=True)
    return row


def run_as_optimization_workflow(
    train_dates: Sequence[str],
    test_dates: Sequence[str],
    base_config: Dict[str, Any],
    param_grid: Dict[str, List[Any]] | None = None,
) -> Dict[str, Any]:
    """Run train search, top-5 test validation, and final strategy comparison."""
    param_grid = param_grid or DEFAULT_AS_PARAM_GRID
    optimization_root = _optimization_root(base_config)
    optimization_root.mkdir(parents=True, exist_ok=True)

    train_df = run_as_parameter_search(train_dates, test_dates, param_grid, base_config)
    train_csv_path = optimization_root / "as_param_search_train.csv"
    train_df = pd.read_csv(train_csv_path) if train_csv_path.exists() else train_df
    train_df = train_df.sort_values(["objective_score", "train_sharpe_like"], ascending=[False, False]).reset_index(drop=True)

    top5 = train_df.head(5).copy()
    test_rows: List[Dict[str, Any]] = []

    test_dates_list = _normalize_dates(test_dates)
    print("\nTEST PHASE: Top-5 Validation")
    print("=" * 70)
    test_data = _preload_daily_data(test_dates_list, base_config["data_dir"])
    
    for idx, (_, row) in enumerate(top5.iterrows(), start=1):
        params = _extract_params(row["params"])
        strategy = _build_strategy(params)
        print(f"  [{idx}/5] Evaluating {row['param_key']} on test set...")
        test_summary = _evaluate_strategy_on_test(test_dates_list, strategy, base_config, "as_opt", preloaded_data=test_data)
        test_rows.append(
            {
                "param_key": row["param_key"],
                "params": row["params"],
                "train_objective_score": row["objective_score"],
                "train_sharpe_like": row["train_sharpe_like"],
                "train_win_days_ratio": row["train_win_days_ratio"],
                "train_mean_rebate_share": row["train_mean_rebate_share"],
                "train_mean_inventory_pnl": row["train_mean_inventory_pnl"],
                "test_mean_pnl": test_summary.get("mean_pnl", 0.0),
                "test_std_pnl": test_summary.get("std_pnl", 0.0),
                "test_sharpe_like": test_summary.get("sharpe_like", 0.0),
                "test_win_days_ratio": test_summary.get("win_days_ratio", 0.0),
                "test_total_pnl_sum": test_summary.get("total_pnl_sum", 0.0),
                "test_mean_rebate_share": test_summary.get("mean_rebate_share", 0.0),
                "test_mean_inventory_pnl": test_summary.get("mean_inventory_pnl", 0.0),
                "test_mean_turnover": test_summary.get("mean_turnover", 0.0),
                "test_mean_position": test_summary.get("mean_position", 0.0),
                "test_mean_long_ratio": test_summary.get("mean_long_ratio", 0.0),
                "test_mean_short_ratio": test_summary.get("mean_short_ratio", 0.0),
                "test_worst_day_pnl": test_summary.get("worst_day_pnl", 0.0),
                "test_tail_risk_ratio": test_summary.get("tail_risk_ratio", 0.0),
            }
        )

    top5_df = pd.DataFrame(test_rows)
    top5_test_path = optimization_root / "as_top5_test.csv"
    top5_df.to_csv(top5_test_path, index=False)

    best_row = top5_df.sort_values(["test_sharpe_like", "test_total_pnl_sum"], ascending=[False, False]).iloc[0]
    best_params = _extract_params(best_row["params"])
    best_params_path = optimization_root / "as_best_params.json"
    best_payload = {
        "best_params": best_params,
        "train_row": train_df.loc[train_df["param_key"] == best_row["param_key"], :].iloc[0].to_dict() if not train_df.empty else {},
        "test_row": best_row.to_dict(),
    }
    with best_params_path.open("w", encoding="utf-8") as f:
        json.dump(best_payload, f, ensure_ascii=False, indent=2)

    print("\nFINAL PHASE: Strategy Comparison")
    print("=" * 70)
    final_rows: List[Dict[str, Any]] = []
    baseline_strategies = [
        ("simple", _build_base_strategy("simple", base_config)),
        ("inventory", _build_base_strategy("inventory", base_config)),
        ("as_default", _build_base_strategy("as", base_config)),
        ("as_optimized", _build_strategy(best_params)),
    ]

    for idx, (label, strategy) in enumerate(baseline_strategies, start=1):
        print(f"  [{idx}/4] Evaluating {label} on test set...")
        summary = _evaluate_strategy_on_test(test_dates_list, strategy, base_config, label, preloaded_data=test_data)
        final_rows.append(_summary_row_from_summary(summary, label, params=best_params if label == "as_optimized" else None))

    final_df = pd.DataFrame(final_rows)
    final_path = optimization_root / "final_strategy_comparison.csv"
    final_df.to_csv(final_path, index=False)

    final_report_path = optimization_root / "final_strategy_report.md"
    report_text = _build_final_report(
        best_params=best_params,
        train_df=train_df,
        top5_df=top5_df,
        final_df=final_df,
        best_row=best_row.to_dict(),
    )
    final_report_path.write_text(report_text, encoding="utf-8")

    return {
        "train_csv": str(train_csv_path),
        "top5_test_csv": str(top5_test_path),
        "best_params_json": str(best_params_path),
        "final_comparison_csv": str(final_path),
        "final_report_md": str(final_report_path),
        "train_df": train_df,
        "top5_df": top5_df,
        "final_df": final_df,
        "best_params": best_params,
    }


def _build_final_report(
    best_params: Dict[str, Any],
    train_df: pd.DataFrame,
    top5_df: pd.DataFrame,
    final_df: pd.DataFrame,
    best_row: Dict[str, Any],
) -> str:
    """Create a research-style markdown report."""
    def metric_row(label: str) -> pd.Series:
        return final_df.loc[final_df["strategy"] == label].iloc[0]

    simple_row = metric_row("simple")
    inventory_row = metric_row("inventory")
    as_default_row = metric_row("as_default")
    optimized_row = metric_row("as_optimized")

    sharpe_target = float(optimized_row["sharpe_like"])
    over_target = sharpe_target > 1.5
    overfit = float(best_row.get("train_sharpe_like", 0.0)) > 1.5 and float(best_row.get("test_sharpe_like", 0.0)) < 1.5

    sharpe_improvement = float(optimized_row["sharpe_like"]) - float(as_default_row["sharpe_like"])
    rebate_change = float(optimized_row["mean_rebate_share"]) - float(as_default_row["mean_rebate_share"])
    inventory_change = float(optimized_row["mean_inventory_pnl"]) - float(as_default_row["mean_inventory_pnl"])
    turnover_change = float(optimized_row["mean_turnover"]) - float(as_default_row["mean_turnover"])
    directional_bias_change = abs(float(optimized_row["mean_long_ratio"]) - float(optimized_row["mean_short_ratio"])) - abs(float(as_default_row["mean_long_ratio"]) - float(as_default_row["mean_short_ratio"]))

    lines = []
    lines.append("# Final Strategy Report")
    lines.append("")
    lines.append("## 1. Best Parameters")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(best_params, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    lines.append("## 2. Train Performance")
    lines.append("")
    lines.append(f"- Best train objective score: {float(best_row.get('objective_score', 0.0)):.4f}")
    lines.append(f"- Train Sharpe-like: {float(best_row.get('train_sharpe_like', 0.0)):.4f}")
    lines.append(f"- Train Win Days Ratio: {float(best_row.get('train_win_days_ratio', 0.0)):.2%}")
    lines.append(f"- Train Mean Rebate Share: {float(best_row.get('train_mean_rebate_share', 0.0)):.2%}")
    lines.append(f"- Train Mean Inventory PnL: {float(best_row.get('train_mean_inventory_pnl', 0.0)):.2f}")
    lines.append("")
    lines.append("## 3. Test Performance")
    lines.append("")
    lines.append(f"- Test Sharpe-like: {float(optimized_row['sharpe_like']):.4f}")
    lines.append(f"- Test Mean PnL: {float(optimized_row['mean_pnl']):.2f}")
    lines.append(f"- Test Win Days Ratio: {float(optimized_row['win_days_ratio']):.2%}")
    lines.append(f"- Test Mean Rebate Share: {float(optimized_row['mean_rebate_share']):.2%}")
    lines.append(f"- Test Mean Inventory PnL: {float(optimized_row['mean_inventory_pnl']):.2f}")
    lines.append(f"- Test Mean Turnover: {float(optimized_row['mean_turnover']):.2f}")
    lines.append(f"- Test Mean Position: {float(optimized_row['mean_position']):.2f}")
    lines.append(f"- Test Long/Short Ratio: {float(optimized_row['mean_long_ratio']):.2%} / {float(optimized_row['mean_short_ratio']):.2%}")
    lines.append(f"- Test Worst Day PnL: {float(optimized_row['worst_day_pnl']):.2f}")
    lines.append(f"- Tail Risk Ratio: {float(optimized_row['tail_risk_ratio']):.2f}")
    lines.append("")
    lines.append("## 4. Sharpe Threshold")
    lines.append("")
    lines.append(f"- Sharpe-like > 1.5: {'yes' if over_target else 'no'}")
    lines.append("")
    lines.append("## 5. Overfitting Check")
    lines.append("")
    lines.append(f"- Train Sharpe high but test Sharpe low: {'yes' if overfit else 'no'}")
    lines.append(f"- Train PnL high but test PnL poor: {'yes' if float(best_row.get('train_mean_pnl', 0.0)) > 0 and float(optimized_row['mean_pnl']) < float(best_row.get('train_mean_pnl', 0.0)) else 'no'}")
    lines.append("")
    lines.append("## 6. AS Optimized vs Baseline")
    lines.append("")
    lines.append(f"- Sharpe improvement vs AS default: {sharpe_improvement:.4f}")
    lines.append(f"- Rebate dependency change vs AS default: {rebate_change:.4f}")
    lines.append(f"- Inventory PnL change vs AS default: {inventory_change:.2f}")
    lines.append(f"- Turnover change vs AS default: {turnover_change:.2f}")
    lines.append(f"- Directional bias change vs AS default: {directional_bias_change:.4f}")
    lines.append("")
    lines.append("## 7. Baseline Comparison")
    lines.append("")
    comparison_table = final_df[["strategy", "mean_pnl", "sharpe_like", "win_days_ratio", "mean_rebate_share", "mean_inventory_pnl", "mean_turnover", "mean_position", "mean_long_ratio", "mean_short_ratio", "worst_day_pnl", "tail_risk_ratio"]].copy()
    lines.append("```text")
    lines.append(comparison_table.to_string(index=False))
    lines.append("```")
    lines.append("")
    lines.append("## 8. Interpretation")
    lines.append("")
    lines.append(f"- Stable profitability: {'yes' if float(optimized_row['win_days_ratio']) >= 0.5 else 'no'}")
    lines.append(f"- Rebate dependent: {'yes' if float(optimized_row['mean_rebate_share']) > 0.75 else 'no'}")
    lines.append(f"- Directional bias present: {'yes' if abs(float(optimized_row['mean_long_ratio']) - float(optimized_row['mean_short_ratio'])) > 0.2 else 'no'}")
    lines.append(f"- Tail risk elevated: {'yes' if float(optimized_row['tail_risk_ratio']) > 3.0 else 'no'}")
    lines.append("")
    lines.append("## 9. Notes")
    lines.append("")
    lines.append("- Train split: 2026-01-01 to 2026-01-20")
    lines.append("- Test split: 2026-01-21 to 2026-01-31")
    lines.append("- Parameter search uses only train set")
    lines.append("- Top 5 candidates are evaluated on test without re-optimizing")
    lines.append("- No fill model changes were used to manufacture returns")

    return "\n".join(lines) + "\n"
