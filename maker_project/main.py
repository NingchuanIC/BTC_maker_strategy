"""Main entry point for maker strategy backtesting."""

from __future__ import annotations

import argparse
import sys
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .backtest import (
    BacktestEngine,
    iter_dates,
    load_processed_data,
    plot_results,
    print_metrics,
    print_debug_statistics,
    run_batch,
    save_summary,
    print_summary_report,
    summarize_results,
)
from .configs.default_config import (
    DEFAULT_ALPHA_WEIGHT,
    DEFAULT_BASE_SPREAD,
    DEFAULT_DATA_DIR,
    DEFAULT_END_DATE,
    DEFAULT_FILL_MODEL,
    DEFAULT_FIG_PATH,
    DEFAULT_GAMMA,
    DEFAULT_IMBALANCE_WEIGHT,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_INV_WEIGHT,
    DEFAULT_LOG_PATH,
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
    DEFAULT_PARAM_SAMPLES,
    DEFAULT_TRAIN_START_DATE,
    DEFAULT_TRAIN_END_DATE,
    DEFAULT_TEST_START_DATE,
    DEFAULT_TEST_END_DATE,
    DEFAULT_MICROPRICE_WEIGHT,
    DEFAULT_IMBALANCE_SIGNAL_WEIGHT,
    DEFAULT_INVENTORY_WEIGHT,
    DEFAULT_TARGET_SCALE,
    DEFAULT_INVENTORY_SPREAD_WEIGHT,
    DEFAULT_MIN_TRADE_SPREAD,
    DEFAULT_EDGE_THRESHOLD,
    DEFAULT_RETURN_WINDOW,
    DEFAULT_VOL_THRESHOLD,
    DEFAULT_SIZE_SKEW,
)
from .strategies import (
    ASMarketMakingStrategy,
    InventoryAwareMakerStrategy,
    ASOptimizedMarketMakingStrategy,
    SimpleMakerStrategy,
    SkewAwareMakerStrategy,
)
from .research import DEFAULT_AS_PARAM_GRID, run_as_optimization_workflow


class Tee:
    """Duplicate output to multiple streams."""
    
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text: str) -> int:
        for stream in self.streams:
            stream.write(text)
            stream.flush()
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def parse_strategy_list(strategy_value: str) -> list[str]:
    """Parse a comma-separated list of strategy keys."""
    strategies = [item.strip() for item in strategy_value.split(",") if item.strip()]
    return strategies or [strategy_value.strip()]


def build_strategy(strategy_key: str, args: argparse.Namespace):
    """Create a strategy instance from a strategy key."""
    if strategy_key == "simple":
        return SimpleMakerStrategy(order_size=args.order_size, max_spread=args.max_spread)
    if strategy_key == "inventory":
        return InventoryAwareMakerStrategy(order_size=args.order_size, max_spread=args.max_spread)
    if strategy_key == "skew":
        return SkewAwareMakerStrategy(
            order_size=args.order_size,
            max_spread=args.max_spread,
            alpha=args.alpha,
        )
    if strategy_key == "as":
        return ASMarketMakingStrategy(
            order_size=args.order_size,
            max_spread=args.max_spread,
            tick_size=args.tick_size,
            gamma=args.gamma,
            base_spread=args.base_spread,
            vol_weight=args.vol_weight,
            inv_weight=args.inv_weight,
            alpha_weight=args.alpha_weight,
            imbalance_weight=args.imbalance_weight,
            min_spread=args.min_spread,
        )
    if strategy_key == "robust":
        from .strategies.robust_microprice_as import RobustMicropriceASStrategy

        return RobustMicropriceASStrategy(
            order_size=args.order_size,
            max_spread=args.max_spread,
            tick_size=args.tick_size,
            microprice_weight=args.microprice_weight,
            imbalance_weight=args.imbalance_weight_param,
            inventory_weight=args.inventory_weight,
            target_scale=args.target_scale,
            base_spread=args.base_spread,
            vol_weight=args.vol_weight,
            inventory_spread_weight=args.inventory_spread_weight,
            min_trade_spread=args.min_trade_spread,
            edge_threshold=args.edge_threshold,
            return_window=args.return_window,
            vol_window=args.vol_window,
            vol_threshold=args.vol_threshold_robust,
            size_skew=args.size_skew,
            max_position=args.max_position,
            max_spread_param=args.max_spread,
        )
    raise ValueError(f"Unknown strategy: {strategy_key}")


def strategy_display_name(strategy_key: str) -> str:
    """Return a human-friendly strategy label."""
    return "AS" if strategy_key == "as" else strategy_key.title()


def build_engine_config(args: argparse.Namespace, strategy_key: str) -> dict:
    """Build shared config for batch or single-day execution."""
    return {
        "data_dir": args.data_dir,
        "results_dir": args.results_dir,
        "strategy_name": strategy_key,
        "initial_capital": args.initial_capital,
        "rebate_bps": args.rebate_bps,
        "fill_model": args.fill_model,
        "max_position": args.max_position,
        "sample_n": args.sample_n,
        "vol_window": args.vol_window,
        "short_return_window": args.short_return_window,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run maker strategy backtest and save logs/plots."
    )
    
    # Data and I/O
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing processed CSV files",
    )
    parser.add_argument(
        "--log-path",
        type=str,
        default=str(DEFAULT_LOG_PATH),
        help="Path to output log file",
    )
    parser.add_argument(
        "--fig-path",
        type=str,
        default=str(DEFAULT_FIG_PATH),
        help="Path to output figure file",
    )
    parser.add_argument(
        "--save-results-path",
        type=str,
        default=None,
        help="Optional path to save results CSV",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory to store daily and summary results",
    )
    
    # Backtest parameters
    parser.add_argument(
        "--sample-n",
        type=int,
        default=DEFAULT_SAMPLE_N,
        help="Number of rows to use for backtest",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=DEFAULT_INITIAL_CAPITAL,
        help="Initial capital",
    )
    parser.add_argument(
        "--rebate-bps",
        type=float,
        default=DEFAULT_REBATE_BPS,
        help="Maker rebate in bps",
    )
    parser.add_argument(
        "--fill-model",
        type=str,
        default=DEFAULT_FILL_MODEL,
        choices=["cross", "touch"],
        help="Fill model: cross (price cross) or touch (queue size reduction)",
    )
    parser.add_argument(
        "--order-size",
        type=float,
        default=DEFAULT_ORDER_SIZE,
        help="Order size per quote",
    )
    parser.add_argument(
        "--max-spread",
        type=float,
        default=DEFAULT_MAX_SPREAD,
        help="Maximum spread threshold in bps",
    )
    parser.add_argument(
        "--max-position",
        type=float,
        default=DEFAULT_MAX_POSITION,
        help="Maximum position size",
    )
    
    # Engine parameters
    parser.add_argument(
        "--vol-window",
        type=int,
        default=DEFAULT_VOL_WINDOW,
        help="Window size for volatility calculation",
    )
    parser.add_argument(
        "--short-return-window",
        type=int,
        default=DEFAULT_SHORT_RETURN_WINDOW,
        help="Window size for short-term return calculation",
    )
    
    # Strategy selection
    parser.add_argument(
        "--strategy",
        type=str,
        default="inventory",
        help="Strategy key or comma-separated list, e.g. simple,inventory,as",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run daily backtests across the date range instead of a single aggregated run",
    )
    parser.add_argument(
        "--optimize-as",
        action="store_true",
        help="Run AS parameter optimization and robust validation workflow",
    )
    parser.add_argument(
        "--param-samples",
        type=int,
        default=DEFAULT_PARAM_SAMPLES,
        help="Number of random AS parameter combinations to evaluate",
    )
    parser.add_argument(
        "--train-start-date",
        type=str,
        default=DEFAULT_TRAIN_START_DATE,
        help="Optimization train start date",
    )
    parser.add_argument(
        "--train-end-date",
        type=str,
        default=DEFAULT_TRAIN_END_DATE,
        help="Optimization train end date",
    )
    parser.add_argument(
        "--test-start-date",
        type=str,
        default=DEFAULT_TEST_START_DATE,
        help="Optimization test start date",
    )
    parser.add_argument(
        "--test-end-date",
        type=str,
        default=DEFAULT_TEST_END_DATE,
        help="Optimization test end date",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=DEFAULT_START_DATE,
        help="Batch start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=DEFAULT_END_DATE,
        help="Batch end date in YYYY-MM-DD format",
    )
    
    # SkewAwareMakerStrategy parameters
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.3,
        help="Skew adjustment alpha (for SkewAwareMakerStrategy)",
    )
    
    # ASMarketMakingStrategy parameters
    parser.add_argument(
        "--tick-size",
        type=float,
        default=DEFAULT_TICK_SIZE,
        help="Minimum price increment for AS strategy",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=DEFAULT_GAMMA,
        help="Inventory-based spread coefficient for AS strategy",
    )
    parser.add_argument(
        "--base-spread",
        type=float,
        default=DEFAULT_BASE_SPREAD,
        help="Base spread for AS strategy",
    )
    parser.add_argument(
        "--vol-weight",
        type=float,
        default=DEFAULT_VOL_WEIGHT,
        help="Weight for volatility in spread calculation (AS strategy)",
    )
    parser.add_argument(
        "--inv-weight",
        type=float,
        default=DEFAULT_INV_WEIGHT,
        help="Weight for inventory in reservation price (AS strategy)",
    )
    parser.add_argument(
        "--alpha-weight",
        type=float,
        default=DEFAULT_ALPHA_WEIGHT,
        help="Weight for short-term return in alpha signal (AS strategy)",
    )
    parser.add_argument(
        "--imbalance-weight",
        type=float,
        default=DEFAULT_IMBALANCE_WEIGHT,
        help="Weight for order book imbalance in alpha signal (AS strategy)",
    )
    parser.add_argument(
        "--min-spread",
        type=float,
        default=DEFAULT_MIN_SPREAD,
        help="Minimum spread to maintain (AS strategy)",
    )
    parser.add_argument(
        "--vol-threshold",
        type=float,
        default=None,
        help="Volatility threshold for AS optimized strategy (None disables filter)",
    )
    parser.add_argument(
        "--alpha-to-position-scale",
        type=float,
        default=0.2,
        help="Scale factor mapping alpha signal to target inventory",
    )
    parser.add_argument(
        "--size-skew",
        type=float,
        default=1.5,
        help="Order size skew factor for AS optimized strategy",
    )
    # Robust strategy parameters
    parser.add_argument(
        "--microprice-weight",
        type=float,
        default=DEFAULT_MICROPRICE_WEIGHT,
        help="Weight for microprice edge in reservation price",
    )
    parser.add_argument(
        "--imbalance-weight-param",
        type=float,
        default=DEFAULT_IMBALANCE_SIGNAL_WEIGHT,
        help="Weight for imbalance signal in reservation price",
    )
    parser.add_argument(
        "--inventory-weight",
        type=float,
        default=DEFAULT_INVENTORY_WEIGHT,
        help="Weight for inventory error in reservation price",
    )
    parser.add_argument(
        "--target-scale",
        type=float,
        default=DEFAULT_TARGET_SCALE,
        help="Scale for mapping imbalance to target position",
    )
    parser.add_argument(
        "--inventory-spread-weight",
        type=float,
        default=DEFAULT_INVENTORY_SPREAD_WEIGHT,
        help="Weight for inventory in spread calculation",
    )
    parser.add_argument(
        "--min-trade-spread",
        type=float,
        default=DEFAULT_MIN_TRADE_SPREAD,
        help="Minimum spread to consider trading (robust)",
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=DEFAULT_EDGE_THRESHOLD,
        help="Microprice edge threshold for adverse selection filter",
    )
    parser.add_argument(
        "--return-window",
        type=int,
        default=DEFAULT_RETURN_WINDOW,
        help="Window for recent return calculation",
    )
    parser.add_argument(
        "--vol-threshold-robust",
        type=float,
        default=DEFAULT_VOL_THRESHOLD,
        help="Volatility threshold to disable trading (robust)",
    )
    
    return parser.parse_args()


def _date_list(start_date: str, end_date: str) -> list[str]:
    return list(iter_dates(start_date, end_date))


def run_single_backtest(args: argparse.Namespace, strategy_key: str) -> None:
    """Run the original single-run backtest workflow."""
    log_path = Path(args.log_path)
    fig_path = Path(args.fig_path)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    fig_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as log_file:
        tee = Tee(sys.stdout, log_file)
        with redirect_stdout(tee), redirect_stderr(tee):
            print("=" * 70)
            print("BACKTEST: Maker Strategy")
            print("=" * 70)
            print("Parameters:")
            print(f"  strategy={strategy_key}")
            print(f"  sample_n={args.sample_n}")
            print(f"  fill_model={args.fill_model}")
            print(f"  order_size={args.order_size}")
            print(f"  max_position={args.max_position}")
            print(f"  max_spread={args.max_spread} bps")
            print(f"  rebate_bps={args.rebate_bps} bps")
            print(f"  vol_window={args.vol_window}")
            print(f"  short_return_window={args.short_return_window}")

            if strategy_key == "skew":
                print(f"  alpha={args.alpha}")
            elif strategy_key == "as":
                print(f"  tick_size={args.tick_size}")
                print(f"  gamma={args.gamma}")
                print(f"  base_spread={args.base_spread}")
                print(f"  vol_weight={args.vol_weight}")
                print(f"  inv_weight={args.inv_weight}")
                print(f"  alpha_weight={args.alpha_weight}")
                print(f"  imbalance_weight={args.imbalance_weight}")
                print(f"  min_spread={args.min_spread}")
            print()

            print(f"📊 Loading data from {args.data_dir}...")
            data = load_processed_data(args.data_dir, sample_n=args.sample_n)

            print("\n📊 Data Sample:")
            print(data.head(10))
            print(f"\nData Columns: {list(data.columns)}")
            print(f"Data Types:\n{data.dtypes}\n")

            strategy = build_strategy(strategy_key, args)
            print(f"✓ Strategy created: {strategy.__class__.__name__}")
            print(f"✓ order_size={strategy.order_size}, max_spread={strategy.max_spread}\n")

            print(
                f"📈 Running backtest (first {args.sample_n} rows, "
                f"fill_model={args.fill_model})...\n"
            )
            engine = BacktestEngine(
                data=data,
                strategy=strategy,
                initial_capital=args.initial_capital,
                rebate_bps=args.rebate_bps,
                fill_model=args.fill_model,
                max_position=args.max_position,
                sample_n=args.sample_n,
                vol_window=args.vol_window,
                short_return_window=args.short_return_window,
            )

            results, metrics = engine.run()

            print(f"✓ Backtest completed! Total rows processed: {len(results)}")
            print("\n📊 Results Sample (first 10 rows):")
            print(results[["ts", "mid", "spread", "position", "cash", "equity", "pnl"]].head(10))
            print("\n📊 Results Sample (last 10 rows):")
            print(results[["ts", "mid", "spread", "position", "cash", "equity", "pnl"]].tail(10))

            print_metrics(metrics)
            print_debug_statistics(engine, strategy)

            plot_results(results, metrics, output_path=fig_path)

            if args.save_results_path:
                results_path = Path(args.save_results_path)
                results_path.parent.mkdir(parents=True, exist_ok=True)
                results.to_csv(results_path, index=False)
                print(f"✓ Results saved: {results_path}")

            print(f"✓ Log saved: {log_path}")
            print(f"✓ Figure saved: {fig_path}")


def run_batch_mode(args: argparse.Namespace, strategy_keys: list[str]) -> None:
    """Run daily batch backtests and summary analysis."""
    log_path = Path(args.log_path)
    results_root = Path(args.results_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as log_file:
        tee = Tee(sys.stdout, log_file)
        with redirect_stdout(tee), redirect_stderr(tee):
            print("=" * 70)
            print("BATCH BACKTEST: Maker Strategy")
            print("=" * 70)
            print(f"Date range: {args.start_date} -> {args.end_date}")
            print(f"Strategies: {', '.join(strategy_keys)}")
            print(f"Results dir: {results_root}")
            print(f"sample_n={args.sample_n}")
            print(f"fill_model={args.fill_model}")
            print(f"rebate_bps={args.rebate_bps}")
            print()

            comparison_rows = []

            for strategy_key in strategy_keys:
                print("=" * 70)
                print(f"Running strategy: {strategy_key}")
                print("=" * 70)
                strategy = build_strategy(strategy_key, args)
                config = build_engine_config(args, strategy_key)

                daily_results = run_batch(
                    start_date=args.start_date,
                    end_date=args.end_date,
                    strategy=strategy,
                    config=config,
                )
                summary = summarize_results(daily_results)
                summary["strategy"] = strategy_key
                summary_paths = save_summary(summary, config)
                print_summary_report(summary)
                print(f"✓ Summary saved: {summary_paths['json']}")
                print(f"✓ Summary CSV saved: {summary_paths['csv']}")

                comparison_rows.append(summary)

            if len(comparison_rows) > 1:
                comparison_df = pd.DataFrame(comparison_rows)
                comparison_json = results_root / "comparison_summary.json"
                comparison_csv = results_root / "comparison_summary.csv"
                comparison_df.to_json(comparison_json, orient="records", indent=2, force_ascii=False)
                comparison_df.to_csv(comparison_csv, index=False)
                print("\n" + "=" * 70)
                print("COMPARISON SUMMARY")
                print("=" * 70)
                print(comparison_df[["strategy", "mean_pnl", "win_days_ratio", "mean_rebate_share", "mean_turnover"]].to_string(index=False))
                print(f"✓ Comparison JSON saved: {comparison_json}")
                print(f"✓ Comparison CSV saved: {comparison_csv}")

            print(f"✓ Batch log saved: {log_path}")


def run_optimization_mode(args: argparse.Namespace) -> None:
    """Run AS optimization workflow with train/test validation."""
    log_path = Path(args.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    base_config = {
        "data_dir": args.data_dir,
        "results_dir": args.results_dir,
        "sample_n": args.sample_n,
        "initial_capital": args.initial_capital,
        "rebate_bps": args.rebate_bps,
        "fill_model": args.fill_model,
        "order_size": args.order_size,
        "max_spread": args.max_spread,
        "max_position": args.max_position,
        "vol_window": args.vol_window,
        "short_return_window": args.short_return_window,
        "tick_size": args.tick_size,
        "gamma": args.gamma,
        "base_spread": args.base_spread,
        "vol_weight": args.vol_weight,
        "inv_weight": args.inv_weight,
        "alpha_weight": args.alpha_weight,
        "imbalance_weight": args.imbalance_weight,
        "min_spread": args.min_spread,
        "vol_threshold": args.vol_threshold,
        "alpha_to_position_scale": args.alpha_to_position_scale,
        "size_skew": args.size_skew,
        "param_samples": args.param_samples,
        "random_seed": 42,
    }

    train_dates = _date_list(args.train_start_date, args.train_end_date)
    test_dates = _date_list(args.test_start_date, args.test_end_date)

    with log_path.open("w", encoding="utf-8") as log_file:
        tee = Tee(sys.stdout, log_file)
        with redirect_stdout(tee), redirect_stderr(tee):
            print("=" * 70)
            print("AS OPTIMIZATION WORKFLOW")
            print("=" * 70)
            print(f"Train: {args.train_start_date} -> {args.train_end_date}")
            print(f"Test:  {args.test_start_date} -> {args.test_end_date}")
            print(f"Param samples: {args.param_samples}")
            print(f"Results dir: {args.results_dir}")
            print()

            outputs = run_as_optimization_workflow(
                train_dates=train_dates,
                test_dates=test_dates,
                base_config=base_config,
                param_grid=DEFAULT_AS_PARAM_GRID,
            )

            print("\n✓ Optimization completed")
            print(f"✓ Train CSV: {outputs['train_csv']}")
            print(f"✓ Top-5 Test CSV: {outputs['top5_test_csv']}")
            print(f"✓ Best Params JSON: {outputs['best_params_json']}")
            print(f"✓ Final Comparison CSV: {outputs['final_comparison_csv']}")
            print(f"✓ Final Report MD: {outputs['final_report_md']}")


def main() -> None:
    """Main function to run backtest."""
    args = parse_args()
    strategy_keys = parse_strategy_list(args.strategy)

    if args.optimize_as:
        run_optimization_mode(args)
        return

    if args.batch:
        run_batch_mode(args, strategy_keys)
        return

    if len(strategy_keys) != 1:
        raise ValueError("Multiple strategies require --batch")

    run_single_backtest(args, strategy_keys[0])


if __name__ == "__main__":
    main()
