# Maker Strategy Framework - Quick Start Guide

## Directory Structure

```
q/
├── maker.py                          # Lightweight entry point
├── maker_project/                    # Main project (modular)
│   ├── __init__.py
│   ├── main.py                       # CLI logic
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── models.py                 # Order, Fill, Market, Account
│   │   ├── engine.py                 # BacktestEngine
│   │   ├── data_loader.py            # load_processed_data()
│   │   ├── metrics.py                # Metrics printing
│   │   └── plotting.py               # plot_results()
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py                   # Strategy ABC
│   │   ├── simple_maker.py           # SimpleMakerStrategy
│   │   ├── inventory_maker.py        # InventoryAwareMakerStrategy
│   │   ├── skew_maker.py             # SkewAwareMakerStrategy
│   │   └── as_maker.py               # ASMarketMakingStrategy ⭐ NEW
│   └── configs/
│       └── default_config.py         # Configuration constants
├── okx ob btc 2026-01-processed/     # Data directory
├── maker.log                         # Output log
├── maker_results.png                 # Output plot
├── AS_STRATEGY_RESULTS.md           # Strategy comparison report
└── IMPLEMENTATION_SUMMARY.md        # Original summary
```

## Running Backtests

### Quick Test (1k samples, ~2 seconds)
```bash
python maker.py --strategy simple --sample-n 1000
python maker.py --strategy inventory --sample-n 1000
python maker.py --strategy skew --sample-n 1000
python maker.py --strategy as --sample-n 1000
```

### Full Backtest (100k samples, ~10-15 seconds)
```bash
python maker.py --strategy simple --sample-n 100000
python maker.py --strategy inventory --sample-n 100000
python maker.py --strategy skew --sample-n 100000
python maker.py --strategy as --sample-n 100000
```

### Custom Output Locations
```bash
python maker.py --strategy as --sample-n 100000 \
  --log-path results/as_100k.log \
  --fig-path results/as_100k.png \
  --save-results-path results/as_100k.csv
```

## Strategy-Specific Parameters

### SimpleMakerStrategy
```bash
python maker.py --strategy simple \
  --order-size 0.01 \
  --max-spread 5.0
```

### InventoryAwareMakerStrategy
```bash
python maker.py --strategy inventory \
  --order-size 0.01 \
  --max-spread 5.0
```

### SkewAwareMakerStrategy
```bash
python maker.py --strategy skew \
  --alpha 0.3 \
  --order-size 0.01 \
  --max-spread 5.0
```

### ASMarketMakingStrategy ⭐ NEW
```bash
# Default (balanced)
python maker.py --strategy as --sample-n 100000

# Aggressive on alpha signals
python maker.py --strategy as --sample-n 100000 \
  --alpha-weight 1.0 --imbalance-weight 1.0

# Conservative spreads
python maker.py --strategy as --sample-n 100000 \
  --base-spread 0.5 --gamma 0.05

# High inventory impact
python maker.py --strategy as --sample-n 100000 \
  --gamma 0.2 --inv-weight 2.0

# Volatility-driven
python maker.py --strategy as --sample-n 100000 \
  --vol-weight 2.0 --base-spread 0.1
```

## Common Parameters (All Strategies)

```bash
python maker.py \
  --strategy [simple|inventory|skew|as]        # Strategy choice
  --sample-n 100000                             # Samples to run
  --fill-model [touch|cross]                    # Fill model (default: touch)
  --order-size 0.01                             # Order size per quote
  --max-position 1.0                            # Max position limit
  --max-spread 5.0                              # Spread filter (bps)
  --rebate-bps -0.5                             # Rebate rate (bps)
  --initial-capital 100000                      # Starting capital
  --vol-window 50                               # Volatility lookback
  --short-return-window 10                      # Alpha signal lookback
  --log-path maker.log                          # Log file
  --fig-path maker_results.png                  # Plot file
  --save-results-path results.csv               # CSV export
```

## Output Files

After running a backtest, you get:

1. **maker.log** - Full execution log with all metrics
2. **maker_results.png** - 6-panel visualization:
   - Equity curve
   - Drawdown curve
   - Position over time
   - Spread distribution histogram
   - Cash balance
   - PnL curve

3. **Optional: results.csv** - Time-series backtest data

## Key Metrics Explained

| Metric | Meaning | Target |
|--------|---------|--------|
| total_pnl | Absolute profit/loss | Higher |
| total_return | Return % on initial capital | Higher |
| rebate_share | % PnL from rebates | Lower = Better (real alpha) |
| inventory_pnl | PnL from position management | Higher |
| average_position | Mean position throughout backtest | Depends on strategy |
| long_ratio / short_ratio | % time in long/short positions | Balanced |
| calmar_ratio | Return / Max Drawdown | Higher |
| max_drawdown | Worst peak-to-trough decline | Less negative |
| number_of_trades | Total fills executed | Depends on strategy |
| turnover_ratio | Total notional / Initial capital | Lower = More efficient |

## Strategy Comparison

| Aspect | Simple | Inventory | Skew | AS |
|--------|--------|-----------|------|-----|
| Complexity | Low | Medium | Medium | High |
| Rebate Dependency | 89% | 99% | 99% | 51% ✅ |
| PnL Quality | Fair | Good | Good | **Excellent** |
| Trading Volume | High | High | High | Low ✅ |
| Position Balance | Biased | Biased | Biased | Balanced ✅ |
| Capital Efficiency | Low | Low | Low | **High** ✅ |
| Recommended | No | Testing | Testing | **Yes** |

## Performance Numbers (100k samples)

### SimpleMakerStrategy
- PnL: $587.80 | Rebate: 89.5% | Avg Pos: 0.94 | Trades: 12,085

### InventoryAwareMakerStrategy
- PnL: $526.36 | Rebate: 99.2% | Avg Pos: 0.45 | Trades: 11,910

### SkewAwareMakerStrategy
- PnL: $526.53 | Rebate: 99.1% | Avg Pos: 0.45 | Trades: 11,900

### ASMarketMakingStrategy ⭐ NEW
- PnL: $434.18 | Rebate: 51.2% | Avg Pos: 0.44 | Trades: 5,072
- **48.79% PnL from inventory positioning** (real alpha!)

## Development: Adding Custom Strategies

1. Create new file: `maker_project/strategies/my_strategy.py`
2. Inherit from `Strategy` base class
3. Implement `generate_orders(market, account)` method
4. Add to `maker_project/strategies/__init__.py`
5. Update CLI in `maker_project/main.py`

Example:
```python
from .base import Strategy
from ..backtest.models import Order, Market, Account

class MyCustomStrategy(Strategy):
    def generate_orders(self, market: Market, account: Account):
        orders = []
        # Your logic here
        return orders
```

## Troubleshooting

### No trades executed
- Check spread filter: `--max-spread` might be too tight
- Check position limits: `--max-position` might prevent orders
- Check fill model: `--fill-model touch` vs `cross`

### Low rebate share (AS strategy)
- This is a feature! Means real alpha generation
- If too low, increase `--base-spread` or decrease trading volume

### Want faster computation
- Reduce `--sample-n` (default 100k)
- Test with 1k first, then scale up

### Want different data
- Update `okx ob btc 2026-01-processed/` path in `--data-dir`
- CSV files need columns: ts, best_bid, best_ask, best_bid_size, best_ask_size, mid, spread

---

## Notes

- ✅ All strategies use same BacktestEngine
- ✅ Market features (volatility, imbalance) automatically computed
- ✅ Fill model (touch/cross) applies to all strategies
- ✅ Results and plots saved automatically
- ✅ Backward compatible with original maker.py interface
