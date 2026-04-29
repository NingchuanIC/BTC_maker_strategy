"""Data models for backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Order:
    """Represents an order placed in the market."""
    
    ts: int
    side: str  # "buy" or "sell"
    price: float
    size: float
    order_id: int = 0
    queue_ahead: float = 0  # Size ahead of this order in the queue when placed


@dataclass
class Fill:
    """Represents an executed trade fill."""
    
    ts: int
    side: str  # "buy" or "sell"
    price: float
    size: float
    order_id: int
    rebate: float


@dataclass
class Market:
    """Market snapshot with order book and price data."""
    
    ts: int
    best_bid: float
    best_ask: float
    best_bid_size: float
    best_ask_size: float
    mid: float
    spread: float
    short_term_return: float = 0.0  # mid[t] - mid[t-N] for alpha signal
    volatility: float = 0.0  # volatility from price history
    imbalance: float = 0.0  # (bid_size - ask_size) / (bid_size + ask_size)
    imbalance_ratio: float = 0.0  # bid_size / (bid_size + ask_size)
    microprice: float = 0.0
    microprice_edge: float = 0.0
    recent_return: float = 0.0


@dataclass
class Account:
    """Trading account state."""
    
    cash: float = 0
    position: float = 0
    equity: float = 0
    turnover: float = 0
    rebate: float = 0
    pnl: float = 0
    max_position: float = 1.0

    def copy(self):
        """Create a copy of this account state."""
        return Account(
            cash=self.cash,
            position=self.position,
            equity=self.equity,
            turnover=self.turnover,
            rebate=self.rebate,
            pnl=self.pnl,
            max_position=self.max_position,
        )
