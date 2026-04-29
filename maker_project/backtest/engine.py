"""Backtesting engine for market making strategies."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .models import Order, Fill, Market, Account
from ..strategies import Strategy


class BacktestEngine:
    """Event-driven backtesting engine for maker strategies."""

    def __init__(
        self,
        data: pd.DataFrame,
        strategy: Strategy,
        initial_capital: float = 100000,
        rebate_bps: float = -0.5,
        fill_model: str = "touch",
        max_position: float = 1.0,
        sample_n: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        vol_window: int = 50,
        short_return_window: int = 10,
    ):
        self.data = self._filter_data(data, sample_n, start_time, end_time)
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.rebate_bps = rebate_bps
        self.fill_model = fill_model
        self.max_position = max_position
        self.vol_window = vol_window
        self.short_return_window = short_return_window
        self.records = []
        self.fills = []
        
        # Debug statistics
        self.total_rows = len(self.data)
        self.valid_spread_count = 0
        self.orders_generated_count = 0
        self.pending_orders_count = 0
        self.buy_orders_count = 0
        self.sell_orders_count = 0
        self.buy_fill_count = 0
        self.sell_fill_count = 0

    def _filter_data(
        self,
        data: pd.DataFrame,
        sample_n: Optional[int],
        start_time: Optional[int],
        end_time: Optional[int],
    ) -> pd.DataFrame:
        """Filter data by sample size and time range."""
        df = data.copy()

        if sample_n is not None:
            df = df.iloc[:sample_n]

        if start_time is not None:
            df = df[df["ts"] >= start_time]

        if end_time is not None:
            df = df[df["ts"] <= end_time]

        return df.reset_index(drop=True)

    def _calculate_mid_history(self, mid_history: List[float]) -> Tuple[float, float, float]:
        """Calculate volatility and short-term return from mid price history."""
        volatility = 0.0
        short_term_return = 0.0
        
        if len(mid_history) > self.vol_window:
            # Calculate volatility as std of mid price differences
            mid_array = np.array(mid_history[-self.vol_window:])
            mid_diff = np.diff(mid_array)
            volatility = np.std(mid_diff) if len(mid_diff) > 0 else 0.0
        
        if len(mid_history) > self.short_return_window:
            # Calculate short-term return
            short_term_return = mid_history[-1] - mid_history[-self.short_return_window - 1]
        
        return volatility, short_term_return

    def _calculate_imbalance(self, best_bid_size: float, best_ask_size: float) -> float:
        """Calculate order book imbalance."""
        total_size = best_bid_size + best_ask_size
        if total_size > 0:
            return (best_bid_size - best_ask_size) / total_size
        return 0.0

    def run(self) -> Tuple[pd.DataFrame, Dict]:
        """Run the backtest simulation."""
        account = Account(
            cash=self.initial_capital,
            position=0,
            equity=self.initial_capital,
            turnover=0,
            rebate=0,
            pnl=0,
            max_position=self.max_position,
        )

        pending_orders: List[Order] = []
        mid_history = []  # Track mid prices for volatility and alpha signals

        for i in range(len(self.data) - 1):
            curr_row = self.data.iloc[i]
            next_row = self.data.iloc[i + 1]

            # Build mid history for volatility and short-term return calculation
            mid_history.append(float(curr_row["mid"]))
            if len(mid_history) > max(self.vol_window, self.short_return_window) + 1:
                mid_history.pop(0)

            # Calculate market features
            volatility, short_term_return = self._calculate_mid_history(mid_history)
            imbalance = self._calculate_imbalance(
                float(curr_row["best_bid_size"]),
                float(curr_row["best_ask_size"])
            )
            # compute imbalance ratio and microprice-based features
            total_size = float(curr_row["best_bid_size"]) + float(curr_row["best_ask_size"])
            imbalance_ratio = float(curr_row["best_bid_size"]) / total_size if total_size > 0 else 0.5
            microprice = float(curr_row["best_bid"]) * (1 - imbalance_ratio) + float(curr_row["best_ask"]) * imbalance_ratio
            microprice_edge = microprice - float(curr_row["mid"]) if "mid" in curr_row else 0.0

            market = Market(
                ts=int(curr_row["ts"]),
                best_bid=float(curr_row["best_bid"]),
                best_ask=float(curr_row["best_ask"]),
                best_bid_size=float(curr_row["best_bid_size"]),
                best_ask_size=float(curr_row["best_ask_size"]),
                mid=float(curr_row["mid"]),
                spread=float(curr_row["spread"]),
                short_term_return=short_term_return,
                volatility=volatility,
                imbalance=imbalance,
                imbalance_ratio=imbalance_ratio,
                microprice=microprice,
                microprice_edge=microprice_edge,
                recent_return=short_term_return,
            )

            # Track valid spread rows
            if market.spread > 0 and market.spread <= self.strategy.max_spread:
                self.valid_spread_count += 1

            # Match pending orders against current market
            fills = self._match_orders(pending_orders, curr_row, next_row)

            for fill in fills:
                self._process_fill(account, fill)

            self.fills.extend(fills)
            self.buy_fill_count += sum(1 for f in fills if f.side == "buy")
            self.sell_fill_count += sum(1 for f in fills if f.side == "sell")

            # Generate new orders from strategy
            new_orders = self.strategy.generate_orders(market, account)
            pending_orders = new_orders

            # Track order statistics
            self.orders_generated_count += len(new_orders)
            self.pending_orders_count = len(pending_orders)
            self.buy_orders_count += sum(1 for o in new_orders if o.side == "buy")
            self.sell_orders_count += sum(1 for o in new_orders if o.side == "sell")

            mid = float(curr_row["mid"])
            account.equity = account.cash + account.position * mid + account.rebate
            account.pnl = account.equity - self.initial_capital

            num_buy_fills = sum(1 for f in fills if f.side == "buy")
            num_sell_fills = sum(1 for f in fills if f.side == "sell")

            self.records.append(
                {
                    "ts": market.ts,
                    "mid": mid,
                    "spread": market.spread,
                    "volatility": volatility,
                    "imbalance": imbalance,
                    "short_term_return": short_term_return,
                    "cash": account.cash,
                    "position": account.position,
                    "rebate": account.rebate,
                    "turnover": account.turnover,
                    "equity": account.equity,
                    "pnl": account.pnl,
                    "number_of_fills": len(fills),
                    "buy_filled": num_buy_fills,
                    "sell_filled": num_sell_fills,
                }
            )

        # Final record
        last_row = self.data.iloc[-1]
        total_size = float(last_row["best_bid_size"]) + float(last_row["best_ask_size"]) if ("best_bid_size" in last_row and "best_ask_size" in last_row) else 0
        imbalance_ratio = float(last_row.get("best_bid_size", 0)) / total_size if total_size > 0 else 0.5
        microprice = float(last_row.get("best_bid", 0)) * (1 - imbalance_ratio) + float(last_row.get("best_ask", 0)) * imbalance_ratio
        microprice_edge = microprice - float(last_row.get("mid", 0))

        market = Market(
            ts=int(last_row["ts"]),
            best_bid=float(last_row["best_bid"]),
            best_ask=float(last_row["best_ask"]),
            best_bid_size=float(last_row.get("best_bid_size", 0)),
            best_ask_size=float(last_row.get("best_ask_size", 0)),
            mid=float(last_row["mid"]),
            spread=float(last_row["spread"]),
            short_term_return=0.0,
            volatility=0.0,
            imbalance=0.0,
            imbalance_ratio=imbalance_ratio,
            microprice=microprice,
            microprice_edge=microprice_edge,
            recent_return=0.0,
        )

        account.equity = account.cash + account.position * market.mid + account.rebate
        account.pnl = account.equity - self.initial_capital

        self.records.append(
            {
                "ts": market.ts,
                "mid": market.mid,
                "spread": market.spread,
                "volatility": 0.0,
                "imbalance": 0.0,
                "short_term_return": 0.0,
                "cash": account.cash,
                "position": account.position,
                "rebate": account.rebate,
                "turnover": account.turnover,
                "equity": account.equity,
                "pnl": account.pnl,
                "number_of_fills": 0,
                "buy_filled": 0,
                "sell_filled": 0,
            }
        )

        results_df = pd.DataFrame(self.records)
        metrics = self._calculate_metrics(results_df, account)

        return results_df, metrics

    def _match_orders(self, orders: List[Order], curr_row, next_row) -> List[Fill]:
        """Match pending orders against market movement."""
        fills = []
        next_best_bid = float(next_row["best_bid"])
        next_best_ask = float(next_row["best_ask"])

        if self.fill_model == "cross":
            # Conservative model: price crossing
            for order in orders:
                if order.side == "buy" and next_best_ask <= order.price:
                    traded_notional = order.price * order.size
                    rebate = abs(traded_notional * self.rebate_bps / 10000)
                    fills.append(
                        Fill(
                            ts=int(next_row["ts"]),
                            side="buy",
                            price=order.price,
                            size=order.size,
                            order_id=order.order_id,
                            rebate=rebate,
                        )
                    )
                elif order.side == "sell" and next_best_bid >= order.price:
                    traded_notional = order.price * order.size
                    rebate = abs(traded_notional * self.rebate_bps / 10000)
                    fills.append(
                        Fill(
                            ts=int(next_row["ts"]),
                            side="sell",
                            price=order.price,
                            size=order.size,
                            order_id=order.order_id,
                            rebate=rebate,
                        )
                    )
        
        elif self.fill_model == "touch":
            # Relaxed model: queue size reduction
            curr_best_bid_size = float(curr_row["best_bid_size"])
            curr_best_ask_size = float(curr_row["best_ask_size"])
            next_best_bid_size = float(next_row["best_bid_size"])
            next_best_ask_size = float(next_row["best_ask_size"])

            for order in orders:
                if order.side == "buy":
                    if next_best_ask <= order.price:
                        # ask crossed, full fill
                        traded_notional = order.price * order.size
                        rebate = abs(traded_notional * self.rebate_bps / 10000)
                        fills.append(
                            Fill(
                                ts=int(next_row["ts"]),
                                side="buy",
                                price=order.price,
                                size=order.size,
                                order_id=order.order_id,
                                rebate=rebate,
                            )
                        )
                    elif next_best_bid == order.price and next_best_bid_size < curr_best_bid_size:
                        # Still at best_bid but queue reduced
                        filled_size = min(order.size, curr_best_bid_size - next_best_bid_size)
                        if filled_size > 0:
                            traded_notional = order.price * filled_size
                            rebate = abs(traded_notional * self.rebate_bps / 10000)
                            fills.append(
                                Fill(
                                    ts=int(next_row["ts"]),
                                    side="buy",
                                    price=order.price,
                                    size=filled_size,
                                    order_id=order.order_id,
                                    rebate=rebate,
                                )
                            )
                
                elif order.side == "sell":
                    if next_best_bid >= order.price:
                        # bid crossed, full fill
                        traded_notional = order.price * order.size
                        rebate = abs(traded_notional * self.rebate_bps / 10000)
                        fills.append(
                            Fill(
                                ts=int(next_row["ts"]),
                                side="sell",
                                price=order.price,
                                size=order.size,
                                order_id=order.order_id,
                                rebate=rebate,
                            )
                        )
                    elif next_best_ask == order.price and next_best_ask_size < curr_best_ask_size:
                        # Still at best_ask but queue reduced
                        filled_size = min(order.size, curr_best_ask_size - next_best_ask_size)
                        if filled_size > 0:
                            traded_notional = order.price * filled_size
                            rebate = abs(traded_notional * self.rebate_bps / 10000)
                            fills.append(
                                Fill(
                                    ts=int(next_row["ts"]),
                                    side="sell",
                                    price=order.price,
                                    size=filled_size,
                                    order_id=order.order_id,
                                    rebate=rebate,
                                )
                            )

        return fills

    def _process_fill(self, account: Account, fill: Fill) -> None:
        """Process a fill and update account state."""
        traded_notional = fill.price * fill.size

        if fill.side == "buy":
            account.position += fill.size
            account.cash -= traded_notional
        else:
            account.position -= fill.size
            account.cash += traded_notional

        account.rebate += fill.rebate
        account.turnover += traded_notional

    def _calculate_metrics(self, results_df: pd.DataFrame, account: Account) -> Dict:
        """Calculate comprehensive backtest metrics."""
        metrics: Dict[str, float] = {}

        metrics["total_return"] = (account.equity - self.initial_capital) / self.initial_capital
        metrics["total_pnl"] = account.pnl
        metrics["total_rebate"] = account.rebate
        metrics["total_turnover"] = account.turnover
        metrics["turnover_ratio"] = (
            account.turnover / self.initial_capital
            if self.initial_capital > 0
            else 0
        )
        metrics["final_position"] = account.position
        metrics["final_cash"] = account.cash

        # Inventory PnL breakdown
        metrics["gross_pnl_without_rebate"] = account.pnl - account.rebate
        if abs(account.pnl) > 1e-9:
            metrics["rebate_share"] = (
                account.rebate / abs(account.pnl) if account.pnl != 0 else 0
            )
        else:
            metrics["rebate_share"] = 0
        metrics["inventory_pnl"] = account.pnl - account.rebate

        if account.pnl != 0:
            metrics["inventory_pnl_ratio"] = metrics["inventory_pnl"] / abs(account.pnl)
        else:
            metrics["inventory_pnl_ratio"] = 0
        metrics["pnl_without_rebate"] = account.pnl - account.rebate

        # Drawdown and Calmar ratio
        equity_curve = results_df["equity"].values
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        metrics["max_drawdown"] = np.min(drawdown)

        if metrics["max_drawdown"] < 0:
            metrics["calmar_ratio"] = metrics["total_return"] / abs(metrics["max_drawdown"])
        else:
            metrics["calmar_ratio"] = 0

        # Position statistics
        position_values = results_df["position"].values
        metrics["average_position"] = np.mean(position_values)
        metrics["max_abs_position"] = np.max(np.abs(position_values))
        metrics["position_abs_mean"] = np.mean(np.abs(position_values))
        metrics["position_mean"] = np.mean(position_values)
        metrics["position_std"] = np.std(position_values)

        # Position distribution
        long_count = np.sum(position_values > 1e-9)
        short_count = np.sum(position_values < -1e-9)
        flat_count = np.sum(np.abs(position_values) < 1e-9)
        total_count = len(position_values)

        metrics["long_ratio"] = long_count / total_count if total_count > 0 else 0
        metrics["short_ratio"] = short_count / total_count if total_count > 0 else 0
        metrics["flat_ratio"] = flat_count / total_count if total_count > 0 else 0

        # Time at extremes
        max_pos = account.max_position
        metrics["time_at_max_long"] = np.sum(position_values >= max_pos * 0.99) / len(position_values)
        metrics["time_at_max_short"] = np.sum(position_values <= -max_pos * 0.99) / len(position_values)

        # Returns and Sharpe ratio
        pnl_diff = np.diff(results_df["equity"].values)

        if len(results_df) > 1:
            time_span_ms = results_df["ts"].iloc[-1] - results_df["ts"].iloc[0]
            time_span_days = time_span_ms / (1000 * 60 * 60 * 24) if time_span_ms > 0 else 0
            time_span_years = time_span_days / 365 if time_span_days > 0 else 0

            if time_span_years > 0.001:  # At least ~6 hours
                metrics["annualized_return"] = (
                    (1 + metrics["total_return"]) ** (1 / time_span_years) - 1
                )
            else:
                metrics["annualized_return"] = metrics["total_return"]

            # Tick-level Sharpe (not annualized)
            if len(pnl_diff) > 1:
                returns = pnl_diff / self.initial_capital
                returns_clean = returns[~np.isnan(returns)]

                if len(returns_clean) > 1 and np.std(returns_clean) > 0:
                    metrics["tick_sharpe"] = np.mean(returns_clean) / np.std(returns_clean)
                else:
                    metrics["tick_sharpe"] = 0
            else:
                metrics["tick_sharpe"] = 0
        else:
            metrics["annualized_return"] = 0
            metrics["tick_sharpe"] = 0

        # Trade statistics
        metrics["number_of_trades"] = len(self.fills)

        if len(self.fills) > 0:
            buy_fills = [f for f in self.fills if f.side == "buy"]
            sell_fills = [f for f in self.fills if f.side == "sell"]
            metrics["number_of_buy_trades"] = len(buy_fills)
            metrics["number_of_sell_trades"] = len(sell_fills)

        if len(pnl_diff) > 0:
            metrics["win_rate"] = np.sum(pnl_diff > 0) / len(pnl_diff)
        else:
            metrics["win_rate"] = 0

        return metrics
