"""Summary analysis for batch backtest results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"


def _summary_root(config: Dict[str, Any]) -> Path:
    results_dir = config.get("results_dir")
    if results_dir is None:
        return DEFAULT_RESULTS_DIR / "summary"
    return Path(results_dir) / "summary"


def summarize_results(daily_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate daily metrics into a summary report."""
    if not daily_results:
        return {
            "total_days": 0,
            "mean_pnl": 0.0,
            "std_pnl": 0.0,
            "sharpe_like": 0.0,
            "total_pnl_sum": 0.0,
            "mean_rebate_share": 0.0,
            "mean_inventory_pnl": 0.0,
            "mean_turnover": 0.0,
            "mean_drawdown": 0.0,
            "win_days_ratio": 0.0,
            "worst_day_pnl": 0.0,
            "best_day_pnl": 0.0,
            "mean_long_ratio": 0.0,
            "mean_short_ratio": 0.0,
            "mean_position": 0.0,
            "mean_average_position": 0.0,
            "mean_number_of_trades": 0.0,
        }

    df = pd.DataFrame(daily_results)
    pnl = df["total_pnl"].astype(float)

    std_pnl = float(pnl.std(ddof=0))
    mean_pnl = float(pnl.mean())

    summary: Dict[str, Any] = {
        "strategy": str(df["strategy"].iloc[0]) if "strategy" in df.columns else "unknown",
        "total_days": int(len(df)),
        "mean_pnl": mean_pnl,
        "std_pnl": std_pnl,
        "sharpe_like": mean_pnl / std_pnl if std_pnl > 1e-12 else 0.0,
        "total_pnl_sum": float(pnl.sum()),
        "mean_rebate_share": float(df["rebate_share"].mean()) if "rebate_share" in df else 0.0,
        "mean_inventory_pnl": float(df["inventory_pnl"].mean()) if "inventory_pnl" in df else 0.0,
        "mean_turnover": float(df["turnover_ratio"].mean()) if "turnover_ratio" in df else 0.0,
        "mean_drawdown": float(df["max_drawdown"].mean()) if "max_drawdown" in df else 0.0,
        "win_days_ratio": float((pnl > 0).mean()),
        "worst_day_pnl": float(pnl.min()),
        "best_day_pnl": float(pnl.max()),
        "mean_long_ratio": float(df["long_ratio"].mean()) if "long_ratio" in df else 0.0,
        "mean_short_ratio": float(df["short_ratio"].mean()) if "short_ratio" in df else 0.0,
        "mean_position": float(df["average_position"].mean()) if "average_position" in df else 0.0,
        "mean_average_position": float(df["average_position"].mean()) if "average_position" in df else 0.0,
        "mean_number_of_trades": float(df["number_of_trades"].mean()) if "number_of_trades" in df else 0.0,
    }

    # Extra diagnostics
    summary["tail_risk_ratio"] = (
        abs(summary["worst_day_pnl"]) / summary["mean_pnl"]
        if abs(summary["mean_pnl"]) > 1e-12 and summary["worst_day_pnl"] < 0
        else 0.0
    )
    summary["rebate_dependency_flag"] = summary["mean_rebate_share"] > 0.75
    summary["directional_bias_flag"] = abs(summary["mean_long_ratio"] - summary["mean_short_ratio"]) > 0.2
    summary["stability_flag"] = summary["win_days_ratio"] >= 0.5 and summary["std_pnl"] >= 0.0

    return summary


def save_summary(summary: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, str]:
    """Persist summary JSON and CSV files."""
    summary_root = _summary_root(config)
    summary_root.mkdir(parents=True, exist_ok=True)

    results_root = Path(config.get("results_dir", DEFAULT_RESULTS_DIR))
    results_root.mkdir(parents=True, exist_ok=True)

    strategy_name = str(summary.get("strategy", "unknown")).lower()
    json_path = summary_root / f"{strategy_name}_summary.json"
    csv_path = summary_root / f"{strategy_name}_summary.csv"
    root_json_path = results_root / f"{strategy_name}_summary.json"
    root_csv_path = results_root / f"{strategy_name}_summary.csv"

    for path in [json_path, root_json_path]:
        with path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(csv_path, index=False)
    summary_df.to_csv(root_csv_path, index=False)

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "root_json": str(root_json_path),
        "root_csv": str(root_csv_path),
    }


def print_summary_report(summary: Dict[str, Any]) -> None:
    """Print a research-style summary report."""
    print("\n==============================")
    print("SUMMARY REPORT")
    print("==============================")
    print(f"Strategy: {summary.get('strategy', 'unknown')}")
    print(f"Total Days: {summary.get('total_days', 0)}")
    print(f"Mean PnL: {summary.get('mean_pnl', 0.0):.2f}")
    print(f"Std PnL: {summary.get('std_pnl', 0.0):.2f}")
    print(f"Sharpe-like: {summary.get('sharpe_like', 0.0):.4f}")
    print(f"Win Rate: {summary.get('win_days_ratio', 0.0):.2%}")
    print(f"Worst Day: {summary.get('worst_day_pnl', 0.0):.2f}")
    print(f"Best Day: {summary.get('best_day_pnl', 0.0):.2f}")
    print(f"Rebate Dependency: {summary.get('mean_rebate_share', 0.0):.2%}")
    print(f"Inventory Contribution: {summary.get('mean_inventory_pnl', 0.0):.2f}")
    print(f"Turnover: {summary.get('mean_turnover', 0.0):.2f}")
    print(f"Position Bias: long={summary.get('mean_long_ratio', 0.0):.2%}, short={summary.get('mean_short_ratio', 0.0):.2%}")
    print(f"Tail Risk: {summary.get('tail_risk_ratio', 0.0):.2f}")
    print("==============================")

    stable = summary.get("win_days_ratio", 0.0) >= 0.5
    rebate_dependent = summary.get("mean_rebate_share", 0.0) > 0.75
    biased = abs(summary.get("mean_long_ratio", 0.0) - summary.get("mean_short_ratio", 0.0)) > 0.2
    tail_risky = summary.get("tail_risk_ratio", 0.0) > 3.0

    print("\nInterpretation:")
    print(f"- Stable profitability: {'yes' if stable else 'no'}")
    print(f"- Rebate dependent: {'yes' if rebate_dependent else 'no'}")
    print(f"- Directional bias present: {'yes' if biased else 'no'}")
    print(f"- Tail risk elevated: {'yes' if tail_risky else 'no'}")
