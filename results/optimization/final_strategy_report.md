# Final Strategy Report

## 1. Best Parameters

```json
{
  "alpha_to_position_scale": 0.2,
  "alpha_weight": 0.5,
  "base_spread": 0.1,
  "gamma": 0.05,
  "imbalance_weight": 1.0,
  "inv_weight": 2.0,
  "max_spread": 5.0,
  "min_spread": 0.1,
  "order_size": 0.01,
  "short_return_window": 30,
  "size_skew": 1.5,
  "tick_size": 0.1,
  "vol_threshold": null,
  "vol_weight": 1.5,
  "vol_window": 100
}
```

## 2. Train Performance

- Best train objective score: 0.0000
- Train Sharpe-like: 1.3960
- Train Win Days Ratio: 100.00%
- Train Mean Rebate Share: 42.93%
- Train Mean Inventory PnL: 193.77

## 3. Test Performance

- Test Sharpe-like: 0.5184
- Test Mean PnL: 99.29
- Test Win Days Ratio: 40.00%
- Test Mean Rebate Share: 242.73%
- Test Mean Inventory PnL: -57.44
- Test Mean Turnover: 31.35
- Test Mean Position: 0.67
- Test Long/Short Ratio: 83.18% / 16.78%
- Test Worst Day PnL: -75.44
- Tail Risk Ratio: 0.76

## 4. Sharpe Threshold

- Sharpe-like > 1.5: no

## 5. Overfitting Check

- Train Sharpe high but test Sharpe low: no
- Train PnL high but test PnL poor: no

## 6. AS Optimized vs Baseline

- Sharpe improvement vs AS default: -3.7430
- Rebate dependency change vs AS default: 1.7127
- Inventory PnL change vs AS default: -196.97
- Turnover change vs AS default: -36.89
- Directional bias change vs AS default: 0.6147

## 7. Baseline Comparison

```text
    strategy   mean_pnl  sharpe_like  win_days_ratio  mean_rebate_share  mean_inventory_pnl  mean_turnover  mean_position  mean_long_ratio  mean_short_ratio  worst_day_pnl  tail_risk_ratio
      simple 698.112052     5.855525             1.0           1.228798         -143.926800     168.407770       0.054379         0.526336          0.470738     566.051830         0.000000
   inventory 695.606732     7.936178             1.0           1.188796         -130.679700     165.257286       0.031941         0.546398          0.448382     579.039128         0.000000
  as_default 480.729784     4.261404             1.0           0.714576          139.536600      68.238637      -0.038280         0.472076          0.521370     343.333137         0.000000
as_optimized  99.293262     0.518427             0.4           2.427288          -57.435433      31.345739       0.665863         0.831760          0.167800     -75.441922         0.759789
```

## 8. Interpretation

- Stable profitability: no
- Rebate dependent: yes
- Directional bias present: yes
- Tail risk elevated: no

## 9. Notes

- Train split: 2026-01-01 to 2026-01-20
- Test split: 2026-01-21 to 2026-01-31
- Parameter search uses only train set
- Top 5 candidates are evaluated on test without re-optimizing
- No fill model changes were used to manufacture returns
