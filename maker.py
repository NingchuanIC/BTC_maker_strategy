"""
Maker Strategy Backtesting Framework - Unified Entry Point

This module provides backward compatibility with the original maker.py interface
while delegating to the refactored modular structure under maker_project/.

All strategies and backtesting functionality has been reorganized into:
- maker_project.strategies: SimpleMaker, Inventory, Skew, AS strategies
- maker_project.backtest: Engine, models, data loading, metrics
- maker_project.main: CLI and execution logic
"""

# Import and re-export main function for backward compatibility
from maker_project.main import main

# Also make all classes available at top level for backward compatibility
from maker_project.backtest import (
    Order,
    Fill,
    Market,
    Account,
    BacktestEngine,
    load_processed_data,
    plot_results,
    print_metrics,
    print_debug_statistics,
)
from maker_project.strategies import (
    Strategy,
    SimpleMakerStrategy,
    InventoryAwareMakerStrategy,
    SkewAwareMakerStrategy,
    ASMarketMakingStrategy,
)

__all__ = [
    "main",
    "Order",
    "Fill",
    "Market",
    "Account",
    "BacktestEngine",
    "Strategy",
    "SimpleMakerStrategy",
    "InventoryAwareMakerStrategy",
    "SkewAwareMakerStrategy",
    "ASMarketMakingStrategy",
    "load_processed_data",
    "plot_results",
    "print_metrics",
    "print_debug_statistics",
]


if __name__ == "__main__":
    main()
