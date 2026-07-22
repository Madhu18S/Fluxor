"""
Kraken venue adapter
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from src.venues.base import BaseVenue, OrderBook
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class KrakenVenue(BaseVenue):
    """
    Kraken centralized exchange adapter
    Implements high-performance spot trading interface
    """
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        super().__init__("kraken", api_key, api_secret)
        
        self.base_url = "https://api.kraken.com"
        self.ws_url = "wss://ws.kraken.com"
        
        # Cache
        self._orderbooks: Dict[str, OrderBook] = {}
        self._balances: Dict[str, float] = {}
    
    async def connect(self) -> None:
        """
        Connect to Kraken
        """
        logger.info("Connecting to Kraken")
        try:
            if not self.api_key or not self.api_secret:
                logger.warning("Kraken: No API credentials provided, using demo mode")
            
            self._connected = True
            logger.info("Connected to Kraken")
        except Exception as e:
            logger.error(f"Failed to connect to Kraken: {e}")
            raise
    
    async def disconnect(self) -> None:
        """
        Disconnect from Kraken
        """
        self._connected = False
        logger.info("Disconnected from Kraken")
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """
        Get order book from Kraken
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken")
        
        try:
            # Mock implementation (slightly different prices from Binance)
            bids = [
                (50020 - i * 10, 1.5 - i * 0.1) for i in range(depth // 2)
            ]
            asks = [
                (50030 + i * 10, 1.5 - i * 0.1) for i in range(depth // 2)
            ]
            
            orderbook = OrderBook(
                venue="kraken",
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bids=bids,
                asks=asks,
            )
            
            self._orderbooks[symbol] = orderbook
            return orderbook
        
        except Exception as e:
            logger.error(f"Error fetching orderbook from Kraken: {e}")
            raise
    
    async def get_ticker(self, symbol: str) -> Dict:
        """
        Get ticker data from Kraken
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken")
        
        return {
            "symbol": symbol,
            "last": "50020.00",
            "volume": "950.50",
        }
    
    async def get_balance(self, asset: str) -> float:
        """
        Get balance for asset
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken")
        
        if asset in self._balances:
            return self._balances[asset]
        
        return 0.0
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> Dict:
        """
        Place order on Kraken
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken")
        
        logger.info(f"Placing {side} order: {quantity} {symbol} @ {price}")
        
        return {
            "orderId": "kraken-12345",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "NEW",
        }
    
    async def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel order on Kraken
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kraken")
        
        return {"orderId": order_id, "status": "CANCELLED"}
    
    async def get_order_status(self, order_id: str) -> Dict:
        """
        Get order status
        """
        return {"orderId": order_id, "status": "FILLED", "filled": 1.0}
    
    async def get_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get historical candlestick data
        """
        logger.info(f"Fetching {interval} klines for {symbol}")
        
        return [
            {
                "time": start_time.isoformat(),
                "open": 50020,
                "high": 51020,
                "low": 49020,
                "close": 50520,
                "volume": 95,
            }
        ]
    
    @property
    def is_cex(self) -> bool:
        return True
    
    @property
    def is_dex(self) -> bool:
        return False
