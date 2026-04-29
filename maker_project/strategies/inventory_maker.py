"""Inventory-aware market making strategy."""

from typing import List

from .base import Strategy
from ..backtest.models import Order, Market, Account


class InventoryAwareMakerStrategy(Strategy):
    """
    Inventory-aware maker strategy: restricts orders based on position ratio.
    - Only generates buy orders when position is not too long (inv_ratio < 0.5)
    - Only generates sell orders when position is not too short (inv_ratio > -0.5)
    """

    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        """Generate orders with inventory awareness."""
        orders: List[Order] = []

        if market.spread <= 0 or market.spread > self.max_spread:
            self.skip_spread_count += 1
            return orders

        # Calculate inventory ratio: -1 (short max) to +1 (long max)
        inv_ratio = account.position / account.max_position if account.max_position > 0 else 0

        # Buy order: skip if position too long
        if inv_ratio < 0.5:
            if account.position < account.max_position:
                available_size = min(self.order_size, account.max_position - account.position)
                if available_size > 0:
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
            self.skip_position_buy_count += 1

        # Sell order: skip if position too short
        if inv_ratio > -0.5:
            if account.position > -account.max_position:
                available_size = min(self.order_size, account.position + account.max_position)
                if available_size > 0:
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
            self.skip_position_sell_count += 1

        return orders
