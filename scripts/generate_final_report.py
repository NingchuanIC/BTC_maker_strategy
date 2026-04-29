import pandas as pd
from pathlib import Path

root = Path('d:/imperial_homework/third_year/other/q/results/summary')
final_dir = Path('d:/imperial_homework/third_year/other/q/results/final')
final_dir.mkdir(parents=True, exist_ok=True)

files = {
    'simple': root / 'simple_summary.csv',
    'inventory': root / 'inventory_summary.csv',
    'as': root / 'as_summary.csv',
    'robust': root / 'robust_summary.csv',
}
rows = []
for name, p in files.items():
    if p.exists():
        df = pd.read_csv(p)
        row = df.iloc[0].to_dict()
        row['strategy'] = name
        rows.append(row)

comp = pd.DataFrame(rows)
comp_path = final_dir / 'final_comparison.csv'
comp.to_csv(comp_path, index=False)

# Compute requested answers
best_pnl = comp.loc[comp['mean_pnl'].idxmax()]['strategy'] if not comp.empty else None
best_sharpe = comp.loc[comp['sharpe_like'].idxmax()]['strategy'] if not comp.empty else None
lowest_rebate = comp.loc[comp['mean_rebate_share'].idxmin()]['strategy'] if not comp.empty else None
best_inventory_pnl = comp.loc[comp['mean_inventory_pnl'].idxmax()]['strategy'] if not comp.empty else None
# long/short balance measured by min abs(long_ratio - short_ratio)
comp['ls_balance'] = (comp.get('mean_long_ratio', comp.get('long_ratio', 0)) - comp.get('mean_short_ratio', comp.get('short_ratio', 0))).abs()
most_balanced = comp.loc[comp['ls_balance'].idxmin()]['strategy'] if not comp.empty else None

robust_vs_as = None
robust_row = comp[comp['strategy']=='robust']
as_row = comp[comp['strategy']=='as']
if not robust_row.empty and not as_row.empty:
    robust_sharpe = float(robust_row.iloc[0].get('sharpe_like', 0))
    as_sharpe = float(as_row.iloc[0].get('sharpe_like', 0))
    robust_vs_as = {
        'robust_sharpe': robust_sharpe,
        'as_sharpe': as_sharpe,
        'improved': robust_sharpe > as_sharpe,
    }

report_path = final_dir / 'final_report.md'
with report_path.open('w', encoding='utf-8') as f:
    f.write('# Final Strategy Comparison\n\n')
    f.write('Summary table:\n\n')
    f.write(comp.to_string(index=False))
    f.write('\n\n')
    f.write('## Key Questions\n\n')
    f.write(f'- Highest mean PnL: {best_pnl}\n')
    f.write(f'- Highest Sharpe-like: {best_sharpe}\n')
    f.write(f'- Lowest rebate dependency (mean_rebate_share): {lowest_rebate}\n')
    f.write(f'- Highest inventory_pnl: {best_inventory_pnl}\n')
    f.write(f'- Most balanced long/short: {most_balanced}\n')
    f.write('\n')
    if robust_vs_as is not None:
        f.write('## Robust vs AS\n\n')
        f.write(f"- Robust Sharpe-like: {robust_vs_as['robust_sharpe']:.4f}\n")
        f.write(f"- AS Sharpe-like: {robust_vs_as['as_sharpe']:.4f}\n")
        if robust_vs_as['improved']:
            f.write('- Robust shows higher Sharpe-like than AS on this dataset.\n')
            f.write('- Result still requires validation with trades-based fill simulation.\n')
        else:
            f.write('- Robust strategy improves microstructure logic but does not achieve stable Sharpe > 1.5 under current fill model.\n')
            f.write('- Possible reasons:\n')
            f.write('  - top-of-book data may be insufficient to capture full queue dynamics\n')
            f.write('  - touch fill model is a simplification and may under/over-estimate fills\n')
            f.write('  - a trades-based queue simulation or more detailed matching would be needed for final validation\n')

print('Final files written:', comp_path, report_path)
