"""Skew-aware market making strategy with alpha signal."""

from typing import List

from .base import Strategy
from ..backtest.models import Order, Market, Account


class SkewAwareMakerStrategy(Strategy):
    """
    Skew-aware maker strategy with momentum signal.
    - Combines inventory awareness with short-term return signal
    - Dynamically adjusts order generation thresholds based on price momentum
    """

    def __init__(self, order_size: float = 0.01, max_spread: float = 5.0, alpha: float = 0.3):
        super().__init__(order_size=order_size, max_spread=max_spread)
        self.alpha = alpha  # Signal strength for inventory skew threshold
        self.skip_signal_buy_count = 0
        self.skip_signal_sell_count = 0

    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        """Generate orders with inventory and signal awareness."""
        orders: List[Order] = []

        if market.spread <= 0 or market.spread > self.max_spread:
            self.skip_spread_count += 1
            return orders

        # Calculate inventory ratio: -1 (short max) to +1 (long max)
        inv_ratio = account.position / account.max_position if account.max_position > 0 else 0

        # Alpha signal: momentum-based adjustment to inventory thresholds
        # If price is rising: become more bearish (higher buy threshold to discourage)
        # If price is falling: become more bullish (lower buy threshold to encourage)
        signal_bias = 0.0
        if market.short_term_return > 0:  # Price rising
            signal_bias = self.alpha  # Positive bias = become more bearish
        elif market.short_term_return < 0:  # Price falling
            signal_bias = -self.alpha  # Negative bias = become more bullish

        # Dynamic buy threshold: higher threshold means stricter (less likely to buy)
        buy_threshold = 0.5 + signal_bias  # Range: 0.2 to 0.8
        # Dynamic sell threshold: higher threshold means stricter (more likely to sell)
        sell_threshold = -0.5 - signal_bias  # Range: -0.8 to -0.2

        # Buy order: only if position is not too long
        if inv_ratio < buy_threshold:
            if account.position < account.max_position:
                available_size = min(self.order_size, account.max_position - account.position)
                if available_size > 1e-9:
                    orders.append(
                        Order(
                            ts=market.ts,
                            side="buy",
                            price=market.best_bid,
                            size=available_size,
                            order_id=self.order_id_counter,
                            queue_ahead=market.best_bid_size,
                        )
                    )
                    self.order_id_counter += 1
                    self.generate_order_count += 1
                else:
                    self.skip_position_buy_count += 1
            else:
                self.skip_position_buy_count += 1
        else:
            self.skip_signal_buy_count += 1

        # Sell order: only if position is not too short
        if inv_ratio > sell_threshold:
            if account.position > -account.max_position:
                available_size = min(self.order_size, account.position + account.max_position)
                if available_size > 1e-9:
                    orders.append(
                        Order(
                            ts=market.ts,
                            side="sell",
                            price=market.best_ask,
                            size=available_size,
                            order_id=self.order_id_counter,
                            queue_ahead=market.best_ask_size,
                        )
                    )
                    self.order_id_counter += 1
                    self.generate_order_count += 1
                else:
                    self.skip_position_sell_count += 1
            else:
                self.skip_position_sell_count += 1
        else:
            self.skip_signal_sell_count += 1

        return orders
