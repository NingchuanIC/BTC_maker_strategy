# Final Strategy Comparison

Summary table:

 strategy  total_days   mean_pnl    std_pnl  sharpe_like  total_pnl_sum  mean_rebate_share  mean_inventory_pnl  mean_turnover  mean_drawdown  win_days_ratio  worst_day_pnl  best_day_pnl  mean_long_ratio  mean_short_ratio  mean_position  mean_average_position  mean_number_of_trades  tail_risk_ratio  rebate_dependency_flag  directional_bias_flag  stability_flag  ls_balance
   simple          31 634.236399 282.784326     2.242827   19661.328359           1.444186         -286.600500     184.167380      -0.001399        0.967742    -566.679520   1141.754753         0.490702          0.506794      -0.013379              -0.013379           20329.419355         0.893483                    True                  False            True    0.016092
inventory          31 643.860433 161.047746     3.997948   19959.673426           1.782888         -261.802452     181.132577      -0.000597        1.000000     159.293224    893.992949         0.491489          0.503173      -0.008087              -0.008087           19878.258065         0.000000                    True                  False            True    0.011683
       as          31 437.394582 140.616995     3.110539   13559.232029           0.853339           89.645952      69.549726      -0.000483        1.000000     138.474545    755.313241         0.529145          0.463846       0.031720               0.031720            7636.935484         0.000000                    True                  False            True    0.065298
   robust          31 532.011473 205.743530     2.585799   16492.355650           0.615806          210.429543      64.316386      -0.000250        1.000000     181.858136   1033.935462         0.518034          0.480039       0.022207               0.022207            6065.870968         0.000000                   False                  False            True    0.037995

## Key Questions

- Highest mean PnL: inventory
- Highest Sharpe-like: inventory
- Lowest rebate dependency (mean_rebate_share): robust
- Highest inventory_pnl: robust
- Most balanced long/short: inventory

## Robust vs AS

- Robust Sharpe-like: 2.5858
- AS Sharpe-like: 3.1105
- Robust strategy improves microstructure logic but does not achieve stable Sharpe > 1.5 under current fill model.
- Possible reasons:
  - top-of-book data may be insufficient to capture full queue dynamics
  - touch fill model is a simplification and may under/over-estimate fills
  - a trades-based queue simulation or more detailed matching would be needed for final validation
