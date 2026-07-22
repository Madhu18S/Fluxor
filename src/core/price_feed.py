"""
Price Feed Aggregator
Multi-venue real-time price tracking from CEX and DEX venues
"""

import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

import pandas as pd
from src.utils.logger import setup_logger
from src.venues.base import BaseVenue
from src.network.async_feed import AsyncFeedManager
from src.network.circuit_breaker import CircuitBreaker

logger = setup_logger(__name__)


@dataclass
class PriceSnapshot:
    """Represents a price snapshot at a point in time"""
    timestamp: datetime
    venue: str
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float
    depth: Dict = field(default_factory=dict)

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        if self.mid == 0:
            return 0
        return (self.ask - self.bid) / self.mid

    @property
    def spread_bps(self) -> float:
        """Return spread in basis points"""
        return self.spread * 10000


class PriceFeed:
    """
    Aggregates real-time price feeds from multiple venues
    Handles concurrent updates and maintains order-book depth
    """

    def __init__(
        self,
        venues: List[str],
        update_interval: float = 0.1,
        cache_size: int = 1000,
    ):
        self.venues = venues
        self.update_interval = update_interval
        self.cache_size = cache_size
        
        # Price storage: {venue: {symbol: PriceSnapshot}}
        self.prices: Dict[str, Dict[str, PriceSnapshot]] = {v: {} for v in venues}
        
        # Order book depth cache
        self.order_books: Dict[str, Dict[str, Dict]] = {v: {} for v in venues}
        
        # Async components
        self.feed_manager: Optional[AsyncFeedManager] = None
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            v: CircuitBreaker(venue=v) for v in venues
        }
        
        # State tracking
        self._running = False
        self._subscribers: Dict[str, List] = {}

    async def start(self) -> None:
        """Initialize and start price feed"""
        logger.info(f"Starting price feed for venues: {self.venues}")
        self._running = True
        
        self.feed_manager = AsyncFeedManager(venues=self.venues)
        await self.feed_manager.connect()
        
        # Start update loop
        asyncio.create_task(self._update_loop())
        logger.info("Price feed started successfully")

    async def stop(self) -> None:
        """Stop price feed and cleanup"""
        logger.info("Stopping price feed")
        self._running = False
        
        if self.feed_manager:
            await self.feed_manager.disconnect()

    async def _update_loop(self) -> None:
        """Main update loop for price aggregation"""
        while self._running:
            try:
                # Collect updates from all venues
                updates = await asyncio.gather(
                    *[self._fetch_venue_prices(venue) for venue in self.venues],
                    return_exceptions=True
                )
                
                # Process updates
                for venue, update_data in zip(self.venues, updates):
                    if isinstance(update_data, Exception):
                        logger.error(f"Error fetching prices from {venue}: {update_data}")
                        self.circuit_breakers[venue].record_failure()
                    else:
                        self.circuit_breakers[venue].record_success()
                        await self._process_update(venue, update_data)
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def _fetch_venue_prices(self, venue: str) -> Dict:
        """Fetch prices from a specific venue"""
        if not self.feed_manager:
            return {}
        
        try:
            prices = await self.feed_manager.get_prices(venue)
            return prices
        except Exception as e:
            logger.error(f"Failed to fetch prices from {venue}: {e}")
            return {}

    async def _process_update(self, venue: str, data: Dict) -> None:
        """Process and store price update"""
        for symbol, price_data in data.items():
            snapshot = PriceSnapshot(
                timestamp=datetime.utcnow(),
                venue=venue,
                symbol=symbol,
                bid=price_data.get("bid", 0),
                ask=price_data.get("ask", 0),
                mid=price_data.get("mid", 0),
                volume=price_data.get("volume", 0),
                depth=price_data.get("depth", {}),
            )
            
            self.prices[venue][symbol] = snapshot
            
            # Notify subscribers
            await self._notify_subscribers(symbol, snapshot)

    async def _notify_subscribers(self, symbol: str, snapshot: PriceSnapshot) -> None:
        """Notify subscribers of price updates"""
        if symbol in self._subscribers:
            for callback in self._subscribers[symbol]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(snapshot)
                    else:
                        callback(snapshot)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")

    def get_price(self, venue: str, symbol: str) -> Optional[PriceSnapshot]:
        """Get current price snapshot for a symbol on a venue"""
        return self.prices.get(venue, {}).get(symbol)

    def get_current_prices(self, symbol: str) -> Dict[str, PriceSnapshot]:
        """Get current prices for a symbol across all venues"""
        return {
            venue: self.prices[venue].get(symbol)
            for venue in self.venues
            if symbol in self.prices[venue]
        }

    def get_all_symbols(self) -> Set[str]:
        """Get all available trading symbols"""
        symbols = set()
        for venue_prices in self.prices.values():
            symbols.update(venue_prices.keys())
        return symbols

    def subscribe(self, symbol: str, callback) -> None:
        """Subscribe to price updates for a symbol"""
        if symbol not in self._subscribers:
            self._subscribers[symbol] = []
        self._subscribers[symbol].append(callback)
        logger.debug(f"Subscribed to {symbol} updates")

    def unsubscribe(self, symbol: str, callback) -> None:
        """Unsubscribe from price updates"""
        if symbol in self._subscribers:
            self._subscribers[symbol].remove(callback)

    def get_historical_prices(self, symbol: str, days: int = 1) -> pd.DataFrame:
        """Get historical price data (requires data storage)"""
        # This would fetch from a database
        # Placeholder for future implementation
        pass

    def get_liquidity_depth(self, venue: str, symbol: str) -> Optional[Dict]:
        """Get order-book depth for a symbol"""
        return self.order_books.get(venue, {}).get(symbol)

    def calculate_slippage(self, venue: str, symbol: str, size: float) -> float:
        """Estimate slippage for an order of given size"""
        depth = self.get_liquidity_depth(venue, symbol)
        if not depth:
            return 0
        
        # Simplified slippage calculation based on depth
        asks = depth.get("asks", [])
        cumulative_qty = 0
        
        for price, quantity in asks:
            cumulative_qty += quantity
            if cumulative_qty >= size:
                return (price - depth.get("mid", 0)) / depth.get("mid", 1)
        
        return 0.05  # Default 5% slippage if size exceeds depth

    def is_healthy(self, venue: str) -> bool:
        """Check if a venue's feed is healthy"""
        return not self.circuit_breakers[venue].is_open()

    def get_health_status(self) -> Dict[str, bool]:
        """Get health status of all venues"""
        return {venue: self.is_healthy(venue) for venue in self.venues}
