"""Avellaneda-Stoikov inspired market making strategy."""

import math
from typing import List

from .base import Strategy
from ..backtest.models import Order, Market, Account


class ASMarketMakingStrategy(Strategy):
    """
    Simplified Avellaneda-Stoikov market making strategy.
    
    Core idea:
    - Use reservation price (mid + alpha signal - inventory skew) instead of fixed best_bid/ask
    - Dynamically adjust spread based on volatility and inventory
    - Use order book imbalance and momentum for alpha signals
    
    Parameters:
    - order_size: size of each order
    - max_position: maximum position limit
    - max_spread: maximum spread filter threshold
    - tick_size: minimum price increment for rounding
    - gamma: inventory-based spread coefficient
    - base_spread: base spread in ticks
    - vol_weight: weight for volatility in spread calculation
    - inv_weight: weight for inventory in reservation price
    - alpha_weight: weight for short-term return in alpha signal
    - imbalance_weight: weight for order book imbalance in alpha signal
    - min_spread: minimum spread to maintain
    """

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
    ):
        super().__init__(order_size=order_size, max_spread=max_spread)
        self.tick_size = tick_size
        self.gamma = gamma
        self.base_spread = base_spread
        self.vol_weight = vol_weight
        self.inv_weight = inv_weight
        self.alpha_weight = alpha_weight
        self.imbalance_weight = imbalance_weight
        self.min_spread = min_spread

    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        """
        Generate orders using Avellaneda-Stoikov logic with dynamic spreads.
        """
        orders: List[Order] = []

        # Spread filter: only trade if spread is valid
        if market.spread <= 0 or market.spread > self.max_spread:
            self.skip_spread_count += 1
            return orders

        # Calculate inventory ratio: -1 (short max) to +1 (long max)
        inv_ratio = account.position / account.max_position if account.max_position > 0 else 0

        # Alpha signal combining momentum and imbalance
        alpha_signal = (
            self.alpha_weight * market.short_term_return
            + self.imbalance_weight * market.imbalance
        )

        # Inventory skew adjustment to reservation price
        # Larger position (long or short) pushes reservation price away
        inventory_skew = (
            self.inv_weight * inv_ratio * max(market.volatility, self.tick_size)
        )

        # Reservation price = mid + alpha signal - inventory skew
        # If position is long, move reservation price up (sell more)
        # If position is short, move reservation price down (buy more)
        reservation_price = market.mid + alpha_signal - inventory_skew

        # Dynamic spread based on volatility and inventory
        dynamic_spread = (
            self.base_spread
            + self.vol_weight * market.volatility
            + self.gamma * abs(inv_ratio)
        )
        dynamic_spread = max(dynamic_spread, self.min_spread)

        # Calculate bid and ask quotes around reservation price
        bid_quote = reservation_price - dynamic_spread / 2.0
        ask_quote = reservation_price + dynamic_spread / 2.0

        # Round to tick size
        bid_quote = math.floor(bid_quote / self.tick_size) * self.tick_size
        ask_quote = math.ceil(ask_quote / self.tick_size) * self.tick_size

        # Ensure we remain a maker (don't cross the book)
        if bid_quote > market.best_bid:
            bid_quote = market.best_bid
        if ask_quote < market.best_ask:
            ask_quote = market.best_ask

        # Generate buy order
        if account.position < account.max_position:
            available_size = min(self.order_size, account.max_position - account.position)
            if available_size > 1e-9:
                orders.append(
                    Order(
                        ts=market.ts,
                        side="buy",
                        price=bid_quote,
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

        # Generate sell order
        if account.position > -account.max_position:
            available_size = min(self.order_size, account.position + account.max_position)
            if available_size > 1e-9:
                orders.append(
                    Order(
                        ts=market.ts,
                        side="sell",
                        price=ask_quote,
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
