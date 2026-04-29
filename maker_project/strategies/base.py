"""Abstract base strategy class."""

from abc import ABC, abstractmethod
from typing import List

from ..backtest.models import Order, Market, Account


class Strategy(ABC):
    """Base strategy class that all market making strategies inherit from."""
    
    def __init__(self, order_size: float = 0.01, max_spread: float = 5.0):
        self.order_size = order_size
        self.max_spread = max_spread
        self.order_id_counter = 0
        
        # Debug statistics
        self.skip_spread_count = 0
        self.skip_position_buy_count = 0
        self.skip_position_sell_count = 0
        self.generate_order_count = 0

    @abstractmethod
    def generate_orders(self, market: Market, account: Account) -> List[Order]:
        """Generate orders based on current market and account state."""
        pass
