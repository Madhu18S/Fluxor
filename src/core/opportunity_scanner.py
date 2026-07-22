"""
Arbitrage Opportunity Scanner
Detects cross-exchange and triangular arbitrage opportunities
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
from itertools import combinations, permutations

import numpy as np
from src.utils.logger import setup_logger
from src.core.price_feed import PriceSnapshot

logger = setup_logger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity"""
    opportunity_type: str  # 'cross_exchange' or 'triangular'
    symbol: str
    path: List[Tuple[str, str]]  # [(venue1, symbol1), (venue2, symbol2), ...]
    spread: float  # Profit percentage
    entry_price: float
    exit_price: float
    timestamp: datetime
    estimated_volume: float = 0
    fees_bps: float = 0
    net_profit_bps: float = field(init=False)

    def __post_init__(self):
        self.net_profit_bps = (self.spread * 10000) - self.fees_bps


class OpportunityScanner:
    """
    Scans for arbitrage opportunities across multiple venues
    Supports cross-exchange and triangular arbitrage detection
    """

    def __init__(
        self,
        min_spread: float = 0.002,  # 0.2%
        max_spread: float = 0.015,  # 1.5%
        min_volume: float = 10.0,
        fee_bps: float = 10.0,
    ):
        self.min_spread = min_spread
        self.max_spread = max_spread
        self.min_volume = min_volume
        self.fee_bps = fee_bps
        
        # Opportunity tracking
        self.opportunities: List[ArbitrageOpportunity] = []
        self.executed: Dict[str, ArbitrageOpportunity] = {}

    async def scan(self, prices: Dict[str, Dict[str, PriceSnapshot]]) -> List[ArbitrageOpportunity]:
        """
        Scan for arbitrage opportunities
        prices: {venue: {symbol: PriceSnapshot}}
        """
        opportunities = []
        
        # Get all available symbols
        all_symbols = set()
        for venue_prices in prices.values():
            all_symbols.update(venue_prices.keys())
        
        # Scan for cross-exchange opportunities
        cross_exchange_opps = await self._scan_cross_exchange(prices, all_symbols)
        opportunities.extend(cross_exchange_opps)
        
        # Scan for triangular opportunities
        triangular_opps = await self._scan_triangular(prices, all_symbols)
        opportunities.extend(triangular_opps)
        
        # Filter and rank opportunities
        opportunities = self._rank_opportunities(opportunities)
        self.opportunities = opportunities
        
        return opportunities

    async def _scan_cross_exchange(
        self,
        prices: Dict[str, Dict[str, PriceSnapshot]],
        symbols: set
    ) -> List[ArbitrageOpportunity]:
        """Detect cross-exchange arbitrage (same symbol, different venues)"""
        opportunities = []
        
        for symbol in symbols:
            venue_prices = []
            
            # Collect prices from all venues for this symbol
            for venue, prices_dict in prices.items():
                if symbol in prices_dict:
                    venue_prices.append((venue, prices_dict[symbol]))
            
            if len(venue_prices) < 2:
                continue
            
            # Check all pairs of venues
            for (venue1, price1), (venue2, price2) in combinations(venue_prices, 2):
                # Buy on lower price, sell on higher price
                if price1.ask < price2.bid:
                    spread = (price2.bid - price1.ask) / price1.ask
                    
                    if self.min_spread <= spread <= self.max_spread:
                        opp = ArbitrageOpportunity(
                            opportunity_type="cross_exchange",
                            symbol=symbol,
                            path=[(venue1, symbol), (venue2, symbol)],
                            spread=spread,
                            entry_price=price1.ask,
                            exit_price=price2.bid,
                            timestamp=datetime.utcnow(),
                            estimated_volume=min(price1.volume, price2.volume),
                            fees_bps=self.fee_bps,
                        )
                        opportunities.append(opp)
                
                # Reverse: buy on venue2, sell on venue1
                if price2.ask < price1.bid:
                    spread = (price1.bid - price2.ask) / price2.ask
                    
                    if self.min_spread <= spread <= self.max_spread:
                        opp = ArbitrageOpportunity(
                            opportunity_type="cross_exchange",
                            symbol=symbol,
                            path=[(venue2, symbol), (venue1, symbol)],
                            spread=spread,
                            entry_price=price2.ask,
                            exit_price=price1.bid,
                            timestamp=datetime.utcnow(),
                            estimated_volume=min(price1.volume, price2.volume),
                            fees_bps=self.fee_bps,
                        )
                        opportunities.append(opp)
        
        return opportunities

    async def _scan_triangular(
        self,
        prices: Dict[str, Dict[str, PriceSnapshot]],
        symbols: set
    ) -> List[ArbitrageOpportunity]:
        """Detect triangular arbitrage (e.g., BTC/USD -> ETH/BTC -> ETH/USD)"""
        opportunities = []
        
        # For simplicity, we'll look for triangular opportunities within the same venue
        # In production, this would support cross-venue triangles
        
        for venue in prices.keys():
            venue_symbols = prices[venue].keys()
            
            # Look for symbols that could form triangles
            # E.g., BTC/USD, ETH/USD, ETH/BTC
            for symbol_a, symbol_b, symbol_c in combinations(venue_symbols, 3):
                # Try to form a triangle
                path_pairs = [
                    (symbol_a, symbol_b),
                    (symbol_b, symbol_c),
                    (symbol_c, symbol_a),
                ]
                
                # Check if this forms a valid triangle
                if self._is_valid_triangle(symbol_a, symbol_b, symbol_c, venue_symbols):
                    spread = self._calculate_triangle_spread(
                        prices[venue],
                        symbol_a,
                        symbol_b,
                        symbol_c,
                        venue
                    )
                    
                    if spread and self.min_spread <= spread <= self.max_spread:
                        opp = ArbitrageOpportunity(
                            opportunity_type="triangular",
                            symbol=f"{symbol_a}-{symbol_b}-{symbol_c}",
                            path=[(venue, s) for s in [symbol_a, symbol_b, symbol_c]],
                            spread=spread,
                            entry_price=1.0,
                            exit_price=1.0 + spread,
                            timestamp=datetime.utcnow(),
                            fees_bps=self.fee_bps,
                        )
                        opportunities.append(opp)
        
        return opportunities

    def _is_valid_triangle(self, sym_a: str, sym_b: str, sym_c: str, symbols: set) -> bool:
        """Check if three symbols can form a valid triangle"""
        # Simplified check - in production would verify actual quote/base pairs
        return (sym_a in symbols) and (sym_b in symbols) and (sym_c in symbols)

    def _calculate_triangle_spread(
        self,
        prices: Dict[str, PriceSnapshot],
        sym_a: str,
        sym_b: str,
        sym_c: str,
        venue: str
    ) -> Optional[float]:
        """Calculate profit from a triangular arbitrage"""
        if sym_a not in prices or sym_b not in prices or sym_c not in prices:
            return None
        
        try:
            # Simplified calculation - actual implementation would parse quote/base
            price_a = prices[sym_a].mid
            price_b = prices[sym_b].mid
            price_c = prices[sym_c].mid
            
            # Start with 1 unit of sym_a
            if price_a == 0:
                return None
            
            amt_b = 1.0 / price_a  # Convert to sym_b
            if price_b == 0:
                return None
            
            amt_c = amt_b * price_b  # Convert to sym_c
            final_amt_a = amt_c * price_c  # Convert back to sym_a
            
            profit = (final_amt_a - 1.0) / 1.0
            return max(0, profit)  # Only positive spreads
            
        except Exception as e:
            logger.debug(f"Error calculating triangle spread: {e}")
            return None

    def _rank_opportunities(
        self,
        opportunities: List[ArbitrageOpportunity]
    ) -> List[ArbitrageOpportunity]:
        """Rank opportunities by net profit potential"""
        # Sort by net profit (spread - fees), descending
        return sorted(
            opportunities,
            key=lambda x: x.net_profit_bps,
            reverse=True
        )

    def get_top_opportunities(self, n: int = 10) -> List[ArbitrageOpportunity]:
        """Get top N opportunities by profitability"""
        return self.opportunities[:n]

    def filter_by_type(self, opp_type: str) -> List[ArbitrageOpportunity]:
        """Filter opportunities by type"""
        return [o for o in self.opportunities if o.opportunity_type == opp_type]

    def is_profitable(self, opp: ArbitrageOpportunity) -> bool:
        """Check if opportunity is profitable after fees"""
        return opp.net_profit_bps > 0

    def get_statistics(self) -> Dict:
        """Get statistics about scanned opportunities"""
        if not self.opportunities:
            return {
                "total_opportunities": 0,
                "profitable": 0,
                "avg_spread_bps": 0,
                "max_spread_bps": 0,
            }
        
        spreads_bps = [o.net_profit_bps for o in self.opportunities]
        
        return {
            "total_opportunities": len(self.opportunities),
            "profitable": sum(1 for o in self.opportunities if self.is_profitable(o)),
            "avg_spread_bps": np.mean(spreads_bps),
            "max_spread_bps": np.max(spreads_bps),
            "median_spread_bps": np.median(spreads_bps),
            "by_type": {
                "cross_exchange": len(self.filter_by_type("cross_exchange")),
                "triangular": len(self.filter_by_type("triangular")),
            },
        }
