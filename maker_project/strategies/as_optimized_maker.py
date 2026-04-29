"""Optimized AS market making strategy with aggressiveness controls."""

from __future__ import annotations

import math
from typing import List

from .as_maker import ASMarketMakingStrategy
from ..backtest.models import Order, Market, Account


class ASOptimizedMarketMakingStrategy(ASMarketMakingStrategy):
    """Aggressive AS variant for parameter optimization and stable validation."""

    def __init__(
        self,
        order_size: float = 0.01,
        max_spread: float = 5.0,
        tick_size: float = 0.1,
        gamma: float = 0.1,
        base_spread: float = 0.2,
        vol_weight: float = 1.0,
        inv_weight: float = 1.0,
        alpha_weight: float = 0.5,
        imbalance_weight: float = 0.5,
        min_spread: float = 0.1,
        vol_threshold: float | None = None,
        alpha_to_position_scale: float = 0.2,
        size_skew: float = 1.5,
    ):
        super().__init__(
            order_size=order_size,
            max_spread=max_spread,
            tick_size=tick_size,
            gamma=gamma,
            base_spread=base_spread,
            vol_weight=vol_weight,
            inv_weight=inv_weight,
            alpha_weight=alpha_weight,
            imbalance_weight=imbalance_weight,
            min_spread=min_spread,
        )
        self.vol_threshold = vol_threshold
        self.alpha_to_position_scale = alpha_to_position_scale
        self.size_skew = size_skew

    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        orders: List[Order] = []

        if market.spread <= 0 or market.spread > self.max_spread:
            self.skip_spread_count += 1
            return orders

        inv_ratio = account.position / account.max_position if account.max_position > 0 else 0.0
        alpha_signal = (
            self.alpha_weight * market.short_term_return
            + self.imbalance_weight * market.imbalance
        )

        target_position = max(
            -0.5 * account.max_position,
            min(0.5 * account.max_position, alpha_signal * self.alpha_to_position_scale),
        )
        inventory_error = account.position - target_position

        if self.vol_threshold is not None and market.volatility > self.vol_threshold:
            return []

        reservation_price = market.mid + alpha_signal - (
            self.inv_weight * inventory_error * max(market.volatility, self.tick_size)
        )

        dynamic_spread = (
            self.base_spread
            + self.vol_weight * market.volatility
            + self.gamma * abs(inv_ratio)
        )
        dynamic_spread = max(dynamic_spread, self.min_spread)

        bid_quote = reservation_price - dynamic_spread / 2.0
        ask_quote = reservation_price + dynamic_spread / 2.0
        bid_quote = math.floor(bid_quote / self.tick_size) * self.tick_size
        ask_quote = math.ceil(ask_quote / self.tick_size) * self.tick_size

        if account.position > 0:
            bid_quote = min(bid_quote + self.tick_size, market.best_bid)
            ask_quote = max(ask_quote - self.tick_size, market.best_ask)
        elif account.position < 0:
            bid_quote = min(bid_quote - self.tick_size, market.best_bid)
            ask_quote = max(ask_quote + self.tick_size, market.best_ask)
        else:
            bid_quote = min(bid_quote, market.best_bid)
            ask_quote = max(ask_quote, market.best_ask)

        bid_quote = min(bid_quote, market.best_bid)
        ask_quote = max(ask_quote, market.best_ask)

        if account.position < account.max_position:
            available_size = min(self.order_size, account.max_position - account.position)
            if available_size > 1e-9:
                buy_size = available_size
                sell_size = available_size
                if account.position > target_position:
                    sell_size = min(self.order_size * self.size_skew, account.position + account.max_position)
                    buy_size = min(self.order_size / self.size_skew, account.max_position - account.position)
                elif account.position < target_position:
                    buy_size = min(self.order_size * self.size_skew, account.max_position - account.position)
                    sell_size = min(self.order_size / self.size_skew, account.position + account.max_position)

                if buy_size > 1e-9:
                    orders.append(
                        Order(
                            ts=market.ts,
                            side="buy",
                            price=bid_quote,
                            size=buy_size,
                            order_id=self.order_id_counter,
                            queue_ahead=market.best_bid_size,
                        )
                    )
                    self.order_id_counter += 1
                    self.generate_order_count += 1
                else:
                    self.skip_position_buy_count += 1

                if account.position > -account.max_position and sell_size > 1e-9:
                    orders.append(
                        Order(
                            ts=market.ts,
                            side="sell",
                            price=ask_quote,
                            size=sell_size,
                            order_id=self.order_id_counter,
                            queue_ahead=market.best_ask_size,
                        )
                    )
                    self.order_id_counter += 1
                    self.generate_order_count += 1
                else:
                    self.skip_position_sell_count += 1
            else:
                self.skip_position_buy_count += 1
                self.skip_position_sell_count += 1
        else:
            self.skip_position_buy_count += 1
            self.skip_position_sell_count += 1

        return orders
