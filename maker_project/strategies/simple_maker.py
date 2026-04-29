"""Simple market making strategy (baseline)."""

from typing import List

from .base import Strategy
from ..backtest.models import Order, Market, Account


class SimpleMakerStrategy(Strategy):
    """
    Baseline maker strategy: always quotes both buy and sell at best bid/ask.
    """

    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        """Generate orders: buy at best_bid, sell at best_ask."""
        orders: List[Order] = []

        if market.spread <= 0 or market.spread > self.max_spread:
            self.skip_spread_count += 1
            return orders

        # Buy order with position limit
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

        # Sell order with position limit
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

        return orders
