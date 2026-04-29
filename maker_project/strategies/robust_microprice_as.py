"""Robust Avellaneda-Stoikov variant using microprice and adverse-selection filters."""

from __future__ import annotations

from typing import List

from ..backtest.models import Order, Market, Account
from .base import Strategy


class RobustMicropriceASStrategy(Strategy):
    """Robust AS-style market maker using microprice and simple adverse-selection filters."""

    def __init__(
        self,
        order_size: float = 0.01,
        max_spread: float = 5.0,
        tick_size: float = 0.1,
        microprice_weight: float = 1.0,
        imbalance_weight: float = 0.3,
        inventory_weight: float = 2.0,
        target_scale: float = 0.3,
        base_spread: float = 0.2,
        vol_weight: float = 1.5,
        inventory_spread_weight: float = 0.2,
        min_trade_spread: float = 0.1,
        edge_threshold: float = 0.03,
        return_window: int = 50,
        vol_window: int = 100,
        vol_threshold: float | None = None,
        size_skew: float = 1.5,
        max_position: float = 1.0,
        max_spread_param: float = 5.0,
    ):
        super().__init__(order_size=order_size, max_spread=max_spread_param)
        self.tick_size = tick_size
        self.microprice_weight = microprice_weight
        self.imbalance_weight = imbalance_weight
        self.inventory_weight = inventory_weight
        self.target_scale = target_scale
        self.base_spread = base_spread
        self.vol_weight = vol_weight
        self.inventory_spread_weight = inventory_spread_weight
        self.min_trade_spread = min_trade_spread
        self.edge_threshold = edge_threshold
        self.return_window = return_window
        self.vol_window = vol_window
        self.vol_threshold = vol_threshold
        self.size_skew = size_skew
        self.max_position = max_position

    def _round_tick(self, price: float, side: str) -> float:
        if self.tick_size <= 0:
            return price
        if side == "buy":
            # floor
            import math

            return math.floor(price / self.tick_size) * self.tick_size
        else:
            # sell: ceil
            import math

            return math.ceil(price / self.tick_size) * self.tick_size

    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        orders: List[Order] = []

        # Basic checks: spread and volatility
        if market.spread < self.min_trade_spread:
            self.skip_spread_count += 1
            return []

        if self.vol_threshold is not None and market.volatility > self.vol_threshold:
            # too volatile: widen spreads (we can choose to skip trading)
            self.skip_spread_count += 1
            return []

        # Signals
        imbalance_signal = market.imbalance  # (bid-ask)/(sum)
        imbalance_ratio = market.imbalance_ratio if hasattr(market, "imbalance_ratio") else 0.5
        micro_edge = market.microprice_edge if hasattr(market, "microprice_edge") else 0.0

        # target position scaled from imbalance
        target_pos = max(min(self.target_scale * imbalance_signal, 0.5 * self.max_position), -0.5 * self.max_position)
        inventory_error = account.position - target_pos

        # reservation price uses microprice edge and inventory error
        reservation_price = (
            market.mid
            + self.microprice_weight * micro_edge
            + self.imbalance_weight * imbalance_signal
            - self.inventory_weight * inventory_error * max(market.volatility, self.tick_size)
        )

        # dynamic spread
        dynamic_spread = self.base_spread + self.vol_weight * market.volatility + self.inventory_spread_weight * abs(account.position / max(self.max_position, 1e-9))
        dynamic_spread = max(dynamic_spread, self.min_trade_spread)

        # Adverse selection: if microprice edge strongly positive, avoid selling
        allow_buy = True
        allow_sell = True
        if micro_edge > self.edge_threshold:
            # market biased up -> avoid selling
            allow_sell = False
        elif micro_edge < -self.edge_threshold:
            # market biased down -> avoid buying
            allow_buy = False

        # Quotes
        bid_quote = reservation_price - dynamic_spread / 2
        ask_quote = reservation_price + dynamic_spread / 2

        bid_quote = self._round_tick(bid_quote, "buy")
        ask_quote = self._round_tick(ask_quote, "sell")

        # Ensure maker quotes are at or inside top-of-book constraints
        bid_quote = min(bid_quote, market.best_bid)
        ask_quote = max(ask_quote, market.best_ask)

        # Size skewing
        buy_size = self.order_size
        sell_size = self.order_size
        if account.position > target_pos:
            sell_size = min(self.order_size * self.size_skew, account.position + self.max_position)
            buy_size = max(self.order_size / self.size_skew, 0.0)
        elif account.position < target_pos:
            buy_size = min(self.order_size * self.size_skew, max(self.max_position - account.position, 0.0))
            sell_size = max(self.order_size / self.size_skew, 0.0)

        # Enforce max position limits
        buy_size = max(0.0, min(buy_size, max(self.max_position - account.position, 0.0)))
        sell_size = max(0.0, min(sell_size, max(account.position + self.max_position, 0.0)))

        # Create buy order
        if allow_buy and buy_size > 0 and bid_quote > 0 and dynamic_spread <= self.max_spread:
            self.order_id_counter += 1
            orders.append(Order(ts=0, side="buy", price=bid_quote, size=buy_size, order_id=self.order_id_counter))

        # Create sell order
        if allow_sell and sell_size > 0 and ask_quote > 0 and dynamic_spread <= self.max_spread:
            self.order_id_counter += 1
            orders.append(Order(ts=0, side="sell", price=ask_quote, size=sell_size, order_id=self.order_id_counter))

        self.generate_order_count += len(orders)
        return orders
