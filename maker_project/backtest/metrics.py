"""Utilities for printing backtest metrics."""

from typing import Dict


def print_metrics(metrics: Dict[str, float]) -> None:
    """Print backtest metrics in formatted table."""
    print("\n" + "=" * 60)
    print("BACKTEST METRICS")
    print("=" * 60)
    
    percentage_keys = {
        "total_return", "annualized_return", "tick_sharpe", "win_rate",
        "calmar_ratio", "rebate_share", "time_at_max_long", "time_at_max_short",
        "long_ratio", "short_ratio", "flat_ratio", "max_drawdown",
        "inventory_pnl_ratio"
    }
    
    for key, value in metrics.items():
        if isinstance(value, float):
            if key in percentage_keys:
                print(f"{key:30s}: {value:>15.2%}")
            else:
                print(f"{key:30s}: {value:>15.2f}")
        else:
            print(f"{key:30s}: {value:>15}")
    
    print("=" * 60 + "\n")


def print_debug_statistics(engine, strategy) -> None:
    """Print debug statistics from engine and strategy."""
    print("\n" + "=" * 60)
    print("DEBUG STATISTICS")
    print("=" * 60)
    print(f"Total rows: {engine.total_rows}")
    print(f"Valid spread rows (0 < spread <= max_spread): {engine.valid_spread_count}")
    if engine.total_rows > 0:
        print(f"Valid spread ratio: {engine.valid_spread_count / engine.total_rows:.2%}")
    print(f"Orders generated count: {engine.orders_generated_count}")
    print(f"Buy orders: {engine.buy_orders_count}")
    print(f"Sell orders: {engine.sell_orders_count}")
    print(f"Total buy fills: {engine.buy_fill_count}")
    print(f"Total sell fills: {engine.sell_fill_count}")
    
    if hasattr(strategy, 'skip_spread_count'):
        print(f"\nStrategy Debug:")
        print(f"  Skipped due to spread: {strategy.skip_spread_count}")
        print(f"  Skipped buy due to position: {strategy.skip_position_buy_count}")
        print(f"  Skipped sell due to position: {strategy.skip_position_sell_count}")
        if hasattr(strategy, 'skip_signal_buy_count'):
            print(f"  Skipped buy due to signal: {strategy.skip_signal_buy_count}")
            print(f"  Skipped sell due to signal: {strategy.skip_signal_sell_count}")

    if engine.buy_fill_count + engine.sell_fill_count == 0:
        print(f"\n⚠️  NO TRADES EXECUTED")
        print(f"Possible reasons:")
        print(f"  - Spread filtering: {strategy.skip_spread_count} times")
        print(f"  - Position limits blocked orders")
    
    print("=" * 60 + "\n")
