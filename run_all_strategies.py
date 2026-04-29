"""
Comparison script to run all 4 strategies and generate comparison report.
Usage: python run_all_strategies.py [--sample-n 100000]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
import pandas as pd


def run_strategy(strategy_name, sample_n=100000):
    """Run a single strategy and extract key metrics from log."""
    print(f"\n{'='*70}")
    print(f"Running {strategy_name} strategy (sample_n={sample_n})...")
    print(f"{'='*70}")
    
    cmd = [
        sys.executable, "maker.py",
        "--strategy", strategy_name,
        "--sample-n", str(sample_n),
    ]
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_time
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    print(f"✓ Completed in {elapsed:.1f}s")
    
    return {
        "strategy": strategy_name,
        "sample_n": sample_n,
        "elapsed_seconds": elapsed,
        "return_code": result.returncode,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run all strategies and generate comparison"
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=100000,
        help="Number of samples for backtest"
    )
    args = parser.parse_args()
    
    strategies = ["simple", "inventory", "skew", "as"]
    results = []
    
    print("\n" + "="*70)
    print("MAKER STRATEGY COMPARISON")
    print("="*70)
    print(f"Timestamp: {datetime.now()}")
    print(f"Sample Size: {args.sample_n:,} ticks")
    print(f"Strategies: {', '.join(strategies)}")
    print("="*70)
    
    for strategy in strategies:
        result = run_strategy(strategy, sample_n=args.sample_n)
        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("EXECUTION SUMMARY")
    print("="*70)
    
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))
    
    total_time = results_df["elapsed_seconds"].sum()
    print(f"\nTotal execution time: {total_time:.1f}s")
    print(f"All strategies completed: {all(r['return_code'] == 0 for r in results)}")
    
    # Output locations
    print("\n" + "="*70)
    print("OUTPUT FILES")
    print("="*70)
    print("Log file:        maker.log")
    print("Plot file:       maker_results.png")
    print("Results CSV:     Use --save-results-path to save")
    
    print("\n" + "="*70)
    print("QUICK METRIC COMPARISON")
    print("="*70)
    print("\nFrom the logs above, key metrics:")
    print("- total_pnl: Higher is better")
    print("- rebate_share: Lower is better (more real alpha)")
    print("- inventory_pnl_ratio: Higher is better (less rebate dependent)")
    print("- turnover_ratio: Lower is better (more efficient)")
    print("- long_ratio/short_ratio: Balanced is better")
    print("\nFor detailed comparison, see AS_STRATEGY_RESULTS.md")


if __name__ == "__main__":
    main()
