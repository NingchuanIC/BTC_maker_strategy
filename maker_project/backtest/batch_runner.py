"""Batch backtest runner for daily strategy evaluation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .data_loader import iter_dates, load_processed_data_for_date
from .engine import BacktestEngine


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"


def _build_engine_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract BacktestEngine kwargs from a generic config mapping."""
    return {
        "initial_capital": config.get("initial_capital", 100000),
        "rebate_bps": config.get("rebate_bps", -0.5),
        "fill_model": config.get("fill_model", "touch"),
        "max_position": config.get("max_position", 1.0),
        "sample_n": config.get("sample_n"),
        "vol_window": config.get("vol_window", 50),
        "short_return_window": config.get("short_return_window", 10),
    }


def _results_root(config: Dict[str, Any]) -> Path:
    """Resolve the results directory."""
    results_dir = config.get("results_dir")
    if results_dir is None:
        return DEFAULT_RESULTS_DIR
    return Path(results_dir)


def run_single_day(date: str, strategy, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run one daily backtest and persist metrics to results/daily/."""
    data_dir = config["data_dir"]
    results_root = _results_root(config)
    daily_dir = results_root / "daily"
    save_daily = config.get("save_daily", True)
    if save_daily:
        daily_dir.mkdir(parents=True, exist_ok=True)

    daily_data = load_processed_data_for_date(data_dir, date)
    strategy_instance = copy.deepcopy(strategy)

    engine = BacktestEngine(
        data=daily_data,
        strategy=strategy_instance,
        **_build_engine_config(config),
    )
    results_df, metrics = engine.run()

    daily_metrics: Dict[str, Any] = {
        "date": date,
        "strategy": config.get("strategy_name", strategy.__class__.__name__),
        "total_pnl": float(metrics.get("total_pnl", 0.0)),
        "total_rebate": float(metrics.get("total_rebate", 0.0)),
        "inventory_pnl": float(metrics.get("inventory_pnl", 0.0)),
        "rebate_share": float(metrics.get("rebate_share", 0.0)),
        "turnover_ratio": float(metrics.get("turnover_ratio", 0.0)),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
        "average_position": float(metrics.get("average_position", 0.0)),
        "long_ratio": float(metrics.get("long_ratio", 0.0)),
        "short_ratio": float(metrics.get("short_ratio", 0.0)),
        "number_of_trades": int(metrics.get("number_of_trades", 0)),
        "win_rate": float(metrics.get("win_rate", 0.0)),
        "final_position": float(metrics.get("final_position", 0.0)),
        "position_abs_mean": float(metrics.get("position_abs_mean", 0.0)),
        "time_at_max_long": float(metrics.get("time_at_max_long", 0.0)),
        "time_at_max_short": float(metrics.get("time_at_max_short", 0.0)),
        "total_return": float(metrics.get("total_return", 0.0)),
        "annualized_return": float(metrics.get("annualized_return", 0.0)),
        "turnover": float(metrics.get("total_turnover", 0.0)),
        "rows": int(len(results_df)),
    }

    if save_daily:
        run_label = config.get("run_label") or daily_metrics["strategy"].lower()
        daily_json_path = daily_dir / f"{run_label}_{date}.json"
        with daily_json_path.open("w", encoding="utf-8") as f:
            json.dump(daily_metrics, f, ensure_ascii=False, indent=2)
        daily_metrics["daily_json_path"] = str(daily_json_path)
    return daily_metrics


def run_batch(
    start_date: str,
    end_date: str,
    strategy,
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run daily backtests across an inclusive date range."""
    daily_results: List[Dict[str, Any]] = []
    for date in iter_dates(start_date, end_date):
        daily_results.append(run_single_day(date, strategy, config))
    return daily_results
