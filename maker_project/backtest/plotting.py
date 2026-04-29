"""Plotting utilities for backtest results."""

from pathlib import Path
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_results(
    results_df: pd.DataFrame,
    metrics: Dict,
    output_path: Optional[Path] = None,
    figsize=(14, 12)
) -> None:
    """Plot comprehensive backtest results."""
    fig, axes = plt.subplots(3, 2, figsize=figsize)
    fig.suptitle("Maker Strategy Backtest Results", fontsize=14, fontweight="bold")

    # Equity curve
    ax = axes[0, 0]
    ax.plot(results_df["equity"], label="Equity", linewidth=1.5)
    ax.axhline(y=results_df["equity"].iloc[0], color="r", linestyle="--", alpha=0.5, label="Initial")
    ax.set_title("Equity Curve")
    ax.set_ylabel("Equity ($)")
    ax.legend()
    ax.grid(alpha=0.3)

    # Drawdown curve
    ax = axes[0, 1]
    equity_curve = results_df["equity"].values
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - running_max) / running_max * 100
    ax.plot(drawdown, label="Drawdown", linewidth=1.5, color="red")
    ax.fill_between(range(len(drawdown)), drawdown, 0, alpha=0.3, color="red")
    ax.set_title("Drawdown Curve")
    ax.set_ylabel("Drawdown (%)")
    ax.legend()
    ax.grid(alpha=0.3)

    # Position curve
    ax = axes[1, 0]
    ax.plot(results_df["position"], label="Position", linewidth=1.5, color="green")
    ax.axhline(y=0, color="k", linestyle="-", alpha=0.3)
    ax.set_title("Position Curve")
    ax.set_ylabel("Position (BTC)")
    ax.legend()
    ax.grid(alpha=0.3)

    # Spread distribution
    ax = axes[1, 1]
    spread_valid = results_df[results_df["spread"] > 0]["spread"]
    ax.hist(spread_valid, bins=50, edgecolor="black", alpha=0.7, color="skyblue")
    ax.set_title("Spread Distribution")
    ax.set_xlabel("Spread (bps)")
    ax.set_ylabel("Frequency")
    ax.grid(alpha=0.3, axis="y")

    # Cash curve
    ax = axes[2, 0]
    ax.plot(results_df["cash"], label="Cash", linewidth=1.5, color="purple")
    ax.axhline(y=0, color="r", linestyle="--", alpha=0.5)
    ax.set_title("Cash Curve")
    ax.set_ylabel("Cash ($)")
    ax.legend()
    ax.grid(alpha=0.3)

    # PnL curve
    ax = axes[2, 1]
    ax.plot(results_df["pnl"], label="PnL", linewidth=1.5, color="orange")
    ax.axhline(y=0, color="k", linestyle="-", alpha=0.3)
    ax.fill_between(
        range(len(results_df)),
        results_df["pnl"],
        0,
        where=results_df["pnl"] >= 0,
        interpolate=True,
        alpha=0.3,
        color="green",
        label="Profit",
    )
    ax.fill_between(
        range(len(results_df)),
        results_df["pnl"],
        0,
        where=results_df["pnl"] < 0,
        interpolate=True,
        alpha=0.3,
        color="red",
        label="Loss",
    )
    ax.set_title("PnL Curve")
    ax.set_ylabel("PnL ($)")
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()

    if output_path is not None:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"✓ Figure saved: {output_path}")

    plt.close()
