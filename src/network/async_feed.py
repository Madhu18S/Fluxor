"""
Asynchronous multi-venue price feed manager
Handles concurrent WebSocket connections and L2 order-book reconstruction
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

from src.utils.logger import setup_logger
from src.network.websocket_manager import WebSocketManager
from src.network.circuit_breaker import CircuitBreaker

logger = setup_logger(__name__)


class AsyncFeedManager:
    """
    Manages asynchronous price feeds from multiple venues
    Reconstructs L2 order books and handles concurrent updates
    """
    
    def __init__(
        self,
        venues: List[str],
        buffer_size: int = 10000,
        update_interval: float = 0.01,
    ):
        self.venues = venues
        self.buffer_size = buffer_size
        self.update_interval = update_interval
        
        # WebSocket managers per venue
        self.ws_managers: Dict[str, WebSocketManager] = {
            venue: WebSocketManager(venue) for venue in venues
        }
        
        # Circuit breakers for fault tolerance
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            venue: CircuitBreaker(venue) for venue in venues
        }
        
        # Price buffers
        self.price_buffers: Dict[str, asyncio.Queue] = {
            venue: asyncio.Queue(maxsize=buffer_size) for venue in venues
        }
        
        # Order book snapshots
        self.order_books: Dict[str, Dict] = {}
        
        # State tracking
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def connect(self) -> None:
        """
        Establish connections to all venues
        """
        logger.info(f"Connecting to venues: {self.venues}")
        
        self._running = True
        
        # Connect all venues concurrently
        connect_tasks = [
            self._connect_venue(venue) for venue in self.venues
        ]
        
        results = await asyncio.gather(*connect_tasks, return_exceptions=True)
        
        for venue, result in zip(self.venues, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to {venue}: {result}")
                self.circuit_breakers[venue].open()
            else:
                logger.info(f"Connected to {venue}")

    async def _connect_venue(self, venue: str) -> None:
        """
        Connect to a specific venue and start listening
        """
        try:
            ws_manager = self.ws_managers[venue]
            await ws_manager.connect()
            
            # Start receiving price updates
            task = asyncio.create_task(self._listen_venue(venue))
            self._tasks.append(task)
            
        except Exception as e:
            logger.error(f"Error connecting to {venue}: {e}")
            raise

    async def _listen_venue(self, venue: str) -> None:
        """
        Listen for updates from a venue
        """
        while self._running:
            try:
                ws_manager = self.ws_managers[venue]
                
                # Get latest price update
                update = await asyncio.wait_for(
                    ws_manager.get_update(),
                    timeout=30.0
                )
                
                # Process update
                await self._process_update(venue, update)
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for update from {venue}")
                self.circuit_breakers[venue].record_failure()
                
            except Exception as e:
                logger.error(f"Error listening to {venue}: {e}")
                self.circuit_breakers[venue].record_failure()
                await asyncio.sleep(1)  # Backoff before retry

    async def _process_update(self, venue: str, update: Dict) -> None:
        """
        Process and buffer price update
        """
        try:
            # Extract symbol and prices
            symbol = update.get("symbol")
            if not symbol:
                return
            
            # Reconstruct L2 order book
            order_book = self._reconstruct_orderbook(venue, symbol, update)
            
            # Store in order book cache
            if venue not in self.order_books:
                self.order_books[venue] = {}
            
            self.order_books[venue][symbol] = order_book
            
            # Add to buffer (non-blocking)
            try:
                self.price_buffers[venue].put_nowait({
                    "symbol": symbol,
                    "timestamp": datetime.utcnow(),
                    "data": order_book,
                })
            except asyncio.QueueFull:
                # Drop oldest item if buffer full
                try:
                    self.price_buffers[venue].get_nowait()
                    self.price_buffers[venue].put_nowait({
                        "symbol": symbol,
                        "timestamp": datetime.utcnow(),
                        "data": order_book,
                    })
                except asyncio.QueueEmpty:
                    pass
            
            self.circuit_breakers[venue].record_success()
            
        except Exception as e:
            logger.debug(f"Error processing update from {venue}: {e}")

    def _reconstruct_orderbook(self, venue: str, symbol: str, update: Dict) -> Dict:
        """
        Reconstruct L2 order book from update
        Maintains running delta of bids/asks
        """
        try:
            bids = update.get("bids", [])
            asks = update.get("asks", [])
            
            # Sort bids (highest first) and asks (lowest first)
            sorted_bids = sorted(bids, key=lambda x: float(x[0]), reverse=True)[:20]
            sorted_asks = sorted(asks, key=lambda x: float(x[0]))[:20]
            
            return {
                "symbol": symbol,
                "bids": sorted_bids,
                "asks": sorted_asks,
                "timestamp": datetime.utcnow(),
                "bid": float(sorted_bids[0][0]) if sorted_bids else 0,
                "ask": float(sorted_asks[0][0]) if sorted_asks else 0,
                "mid": (float(sorted_bids[0][0]) + float(sorted_asks[0][0])) / 2 if sorted_bids and sorted_asks else 0,
            }
        except Exception as e:
            logger.debug(f"Error reconstructing orderbook: {e}")
            return {}

    async def get_prices(self, venue: str) -> Dict:
        """
        Get current prices from a venue's buffer
        """
        if venue not in self.price_buffers:
            return {}
        
        prices = {}
        
        # Drain buffer to get latest
        while not self.price_buffers[venue].empty():
            try:
                update = self.price_buffers[venue].get_nowait()
                prices[update["symbol"]] = update["data"]
            except asyncio.QueueEmpty:
                break
        
        return prices

    async def get_orderbook(self, venue: str, symbol: str) -> Optional[Dict]:
        """
        Get current L2 order book for a symbol
        """
        if venue in self.order_books and symbol in self.order_books[venue]:
            return self.order_books[venue][symbol]
        return None

    async def disconnect(self) -> None:
        """
        Disconnect from all venues and cleanup
        """
        logger.info("Disconnecting from all venues")
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Close WebSocket connections
        disconnect_tasks = [
            self.ws_managers[venue].disconnect()
            for venue in self.venues
        ]
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        logger.info("Disconnected from all venues")

    def get_health_status(self) -> Dict[str, bool]:
        """
        Get connection health status for all venues
        """
        return {
            venue: not self.circuit_breakers[venue].is_open()
            for venue in self.venues
        }

    def get_buffer_stats(self) -> Dict[str, int]:
        """
        Get current buffer statistics
        """
        return {
            venue: self.price_buffers[venue].qsize()
            for venue in self.venues
        }
