"""
Venue base class and interface
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrderBook:
    """Represents an order book snapshot"""
    venue: str
    symbol: str
    timestamp: datetime
    bids: List[Tuple[float, float]]  # [(price, quantity), ...]
    asks: List[Tuple[float, float]]
    
    @property
    def bid(self) -> float:
        return self.bids[0][0] if self.bids else 0
    
    @property
    def ask(self) -> float:
        return self.asks[0][0] if self.asks else 0
    
    @property
    def mid(self) -> float:
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return 0
    
    @property
    def spread(self) -> float:
        if self.mid == 0:
            return 0
        return (self.ask - self.bid) / self.mid


class BaseVenue(ABC):
    """
    Abstract base class for exchange/DEX venues
    Defines common interface for all venues
    """
    
    def __init__(self, name: str, api_key: str = "", api_secret: str = ""):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to venue"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to venue"""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get current order book for symbol"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker data"""
        pass
    
    @abstractmethod
    async def get_balance(self, asset: str) -> float:
        """Get balance for asset"""
        pass
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> Dict:
        """Place an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict:
        """Get status of an order"""
        pass
    
    @abstractmethod
    async def get_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Get historical candlestick data"""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def is_cex(self) -> bool:
        """Is this a centralized exchange?"""
        return True
    
    @property
    def is_dex(self) -> bool:
        """Is this a decentralized exchange?"""
        return False
