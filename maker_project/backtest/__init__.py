"""Backtesting framework components."""

from .engine import BacktestEngine
from .models import Order, Fill, Market, Account
from .data_loader import load_processed_data, iter_dates
from .batch_runner import run_batch, run_single_day
from .summary import summarize_results, save_summary, print_summary_report
from .plotting import plot_results
from .metrics import print_metrics, print_debug_statistics

__all__ = [
    "BacktestEngine",
    "Order",
    "Fill",
    "Market",
    "Account",
    "load_processed_data",
    "iter_dates",
    "run_batch",
    "run_single_day",
    "summarize_results",
    "save_summary",
    "print_summary_report",
    "plot_results",
    "print_metrics",
    "print_debug_statistics",
]
