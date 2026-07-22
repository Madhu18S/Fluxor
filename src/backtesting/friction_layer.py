"""
Microstructural friction layer for realistic backtesting
Simulates latency, slippage, and fees to eliminate phantom alpha
"""

import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass
from datetime import timedelta
import logging

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class FrictionConfig:
    """Configuration for friction simulation"""
    # Latency
    latency_mean_ms: float = 50.0  # Mean latency in milliseconds
    latency_shape: float = 2.0  # Gamma distribution shape
    latency_scale: float = 0.5  # Gamma distribution scale
    
    # Fees
    maker_fee_bps: float = 2.0  # Basis points
    taker_fee_bps: float = 5.0
    
    # Slippage
    slippage_bps_per_million: float = 0.5  # Slippage per million in notional
    order_book_depth_ratio: float = 0.5  # Ratio of order book depth to use


class FrictionLayer:
    """
    Simulates realistic market microstructure frictions:
    - Network latency (Gamma-distributed)
    - Exchange fees (maker/taker)
    - Order book slippage
    - Discrete price increments (tick size)
    """
    
    def __init__(self, config: FrictionConfig = None):
        self.config = config or FrictionConfig()
        self.rng = np.random.RandomState(seed=42)
        
        # Statistics tracking
        self.total_latency_cost = 0.0
        self.total_fee_cost = 0.0
        self.total_slippage_cost = 0.0
        self.latencies: list = []

    def add_latency(self) -> float:
        """
        Generate latency with Gamma distribution
        Simulates discrete network delays with occasional spikes
        
        Returns:
            Latency in milliseconds
        """
        latency = self.rng.gamma(
            shape=self.config.latency_shape,
            scale=self.config.latency_scale
        )
        latency = max(1.0, latency)  # Minimum 1ms
        self.latencies.append(latency)
        self.total_latency_cost += latency
        return latency

    def calculate_fees(self, notional: float, is_maker: bool = False) -> float:
        """
        Calculate trading fees
        
        Args:
            notional: Order size in USD/notional value
            is_maker: True for maker order, False for taker
        
        Returns:
            Fee in notional currency units
        """
        fee_rate = self.config.maker_fee_bps if is_maker else self.config.taker_fee_bps
        fee = notional * (fee_rate / 10000)  # Convert bps to decimal
        self.total_fee_cost += fee
        return fee

    def calculate_slippage(self, size_usd: float, mid_price: float) -> float:
        """
        Calculate order book slippage
        
        Slippage models the impact of moving through order book depth.
        Uses simplified square-root formula similar to real market impact.
        
        Args:
            size_usd: Order size in USD
            mid_price: Current mid price
        
        Returns:
            Slippage in basis points
        """
        if mid_price == 0:
            return 0
        
        # Size in millions of notional
        size_millions = size_usd / 1_000_000
        
        # Square-root impact model: slippage = k * sqrt(size)
        slippage_bps = self.config.slippage_bps_per_million * np.sqrt(size_millions)
        
        # Add some randomness (order book varies)
        slippage_bps *= self.rng.uniform(0.8, 1.2)
        
        self.total_slippage_cost += (slippage_bps / 10000) * size_usd
        
        return slippage_bps

    def apply_tick_size(self, price: float, tick_size: float = 0.01) -> float:
        """
        Apply minimum tick size (discrete price increments)
        """
        if tick_size <= 0:
            return price
        return round(price / tick_size) * tick_size

    def apply_all_frictions(
        self,
        entry_price: float,
        exit_price: float,
        entry_size: float,
        exit_size: float,
        is_entry_maker: bool = False,
        is_exit_maker: bool = False,
    ) -> Tuple[float, float, Dict]:
        """
        Apply all friction costs to a round-trip trade
        
        Returns:
            (adjusted_entry_price, adjusted_exit_price, friction_details)
        """
        # Latencies (simulate execution delays)
        entry_latency = self.add_latency()
        exit_latency = self.add_latency()
        
        # Price movement due to latency (assume 1 bps per 50ms)
        price_impact_entry = (entry_latency / 50) * 0.0001
        price_impact_exit = (exit_latency / 50) * 0.0001
        
        # Apply slippage
        entry_slippage_bps = self.calculate_slippage(entry_price * entry_size, entry_price)
        exit_slippage_bps = self.calculate_slippage(exit_price * exit_size, exit_price)
        
        # Apply fees
        entry_fee_pct = self.calculate_fees(entry_price * entry_size, is_entry_maker) / (entry_price * entry_size)
        exit_fee_pct = self.calculate_fees(exit_price * exit_size, is_exit_maker) / (exit_price * exit_size)
        
        # Adjusted prices
        # Entry: buy side pays bid-ask spread + slippage + fee impact
        adjusted_entry = entry_price * (1 + price_impact_entry + entry_slippage_bps/10000 + entry_fee_pct)
        
        # Exit: sell side gets worse price + slippage + fee impact
        adjusted_exit = exit_price * (1 - price_impact_exit - exit_slippage_bps/10000 - exit_fee_pct)
        
        details = {
            "entry_latency_ms": entry_latency,
            "exit_latency_ms": exit_latency,
            "entry_slippage_bps": entry_slippage_bps,
            "exit_slippage_bps": exit_slippage_bps,
            "entry_fee": entry_fee_pct * entry_price * entry_size,
            "exit_fee": exit_fee_pct * exit_price * exit_size,
            "total_friction_cost": (adjusted_entry - entry_price) * entry_size - (exit_price - adjusted_exit) * exit_size,
        }
        
        return adjusted_entry, adjusted_exit, details

    def get_statistics(self) -> Dict:
        """
        Get friction statistics
        """
        if not self.latencies:
            return {}
        
        latencies = np.array(self.latencies)
        
        return {
            "total_latency_cost_ms": self.total_latency_cost,
            "total_fee_cost": self.total_fee_cost,
            "total_slippage_cost": self.total_slippage_cost,
            "avg_latency_ms": np.mean(latencies),
            "max_latency_ms": np.max(latencies),
            "p99_latency_ms": np.percentile(latencies, 99),
            "latency_spikes_count": np.sum(latencies > np.mean(latencies) * 2),
        }
