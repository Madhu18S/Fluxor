"""
Historical backtesting simulator
Replays historical market data through trading strategy
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
import logging

from src.utils.logger import setup_logger
from src.core.opportunity_scanner import ArbitrageOpportunity, OpportunityScanner
from src.core.executor import Executor, Trade
from src.backtesting.friction_layer import FrictionLayer, FrictionConfig
from src.backtesting.metrics import BacktestMetrics

logger = setup_logger(__name__)


@dataclass
class BacktestBar:
    """Single candlestick/time period data"""
    timestamp: datetime
    venue: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestSimulator:
    """
    Simulates trading strategy on historical market data
    with realistic microstructural frictions
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        friction_config: Optional[FrictionConfig] = None,
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.friction_layer = FrictionLayer(friction_config or FrictionConfig())
        
        # Data storage
        self.bars: List[BacktestBar] = []
        self.trades: List[Trade] = []
        
        # Performance tracking
        self.metrics = BacktestMetrics()
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.drawdown_curve: List[float] = []
    
    def load_historical_data(self, bars: List[BacktestBar]) -> None:
        """
        Load historical market data
        """
        self.bars = sorted(bars, key=lambda b: b.timestamp)
        logger.info(f"Loaded {len(self.bars)} historical bars")
        
        if self.bars:
            self.metrics.start_date = self.bars[0].timestamp
            self.metrics.end_date = self.bars[-1].timestamp
    
    async def run_backtest(
        self,
        scanner: OpportunityScanner,
        executor: Executor,
        symbol: str = "BTC/USD",
    ) -> BacktestMetrics:
        """
        Run complete backtest simulation
        
        Args:
            scanner: Opportunity scanner
            executor: Trade executor
            symbol: Trading symbol
        
        Returns:
            BacktestMetrics with full performance analysis
        """
        logger.info(f"Starting backtest from {self.metrics.start_date} to {self.metrics.end_date}")
        logger.info(f"Initial capital: ${self.initial_capital:,.2f}")
        
        # Group bars by timestamp
        bars_by_time = {}
        for bar in self.bars:
            if bar.timestamp not in bars_by_time:
                bars_by_time[bar.timestamp] = {}
            bars_by_time[bar.timestamp][bar.venue] = bar
        
        # Replay history
        for timestamp in sorted(bars_by_time.keys()):
            venue_bars = bars_by_time[timestamp]
            
            # Build price snapshot
            prices = self._build_price_snapshot(venue_bars, symbol)
            
            if not prices:
                continue
            
            # Scan for opportunities
            try:
                opportunities = await scanner.scan(prices)
            except:
                continue
            
            # Execute top opportunities
            for opp in opportunities[:3]:  # Execute top 3
                if opp.net_profit_bps <= 0:
                    continue
                
                # Apply frictions
                adjusted_entry, adjusted_exit, friction_details = self.friction_layer.apply_all_frictions(
                    entry_price=opp.entry_price,
                    exit_price=opp.exit_price,
                    entry_size=min(opp.estimated_volume, self.current_capital / opp.entry_price),
                    exit_size=min(opp.estimated_volume, self.current_capital / opp.entry_price),
                )
                
                # Calculate P&L with frictions
                pnl = (adjusted_exit - adjusted_entry) * min(
                    opp.estimated_volume,
                    self.current_capital / opp.entry_price
                )
                
                if pnl > 0:  # Only record if profitable
                    self.current_capital += pnl
                    self.metrics.add_trade(pnl, friction_details.get("entry_fee", 0))
                    self.trades.append(Trade(
                        trade_id=f"bt_{len(self.trades)}",
                        opportunity=opp,
                        pnl=pnl,
                        timestamp=timestamp,
                        status="completed",
                    ))
            
            # Update equity curve
            self.equity_curve.append((timestamp, self.current_capital))
            self.metrics.update_drawdown(self.current_capital)
        
        # Finalize metrics
        self._calculate_final_metrics()
        
        logger.info(f"Backtest complete: {self.metrics.total_trades} trades executed")
        logger.info(f"Final capital: ${self.current_capital:,.2f}")
        logger.info(f"Total P&L: ${self.metrics.total_pnl:,.2f}")
        logger.info(f"Win rate: {self.metrics.win_rate*100:.2f}%")
        
        return self.metrics
    
    def _build_price_snapshot(self, venue_bars: Dict, symbol: str) -> Dict:
        """
        Build price snapshot from venue bars
        """
        from src.core.price_feed import PriceSnapshot
        
        prices = {}
        
        for venue, bar in venue_bars.items():
            snapshot = PriceSnapshot(
                timestamp=bar.timestamp,
                venue=venue,
                symbol=symbol,
                bid=bar.close * 0.9999,
                ask=bar.close * 1.0001,
                mid=bar.close,
                volume=bar.volume,
            )
            prices.setdefault(venue, {})[symbol] = snapshot
        
        return prices
    
    def _calculate_final_metrics(self) -> None:
        """
        Calculate final performance metrics
        """
        if not self.equity_curve:
            return
        
        # Calculate returns
        final_capital = self.equity_curve[-1][1] if self.equity_curve else self.initial_capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital
        self.metrics.cumulative_returns = [total_return]
        
        # Calculate drawdown
        if self.metrics.peak_value > 0 and self.metrics.trough_value > 0:
            max_dd = (self.metrics.peak_value - self.metrics.trough_value) / self.metrics.peak_value
            self.metrics.drawdown_curve.append(max_dd)
    
    def get_equity_curve(self) -> List[Tuple[datetime, float]]:
        """Get equity curve"""
        return self.equity_curve
    
    def get_trades(self) -> List[Trade]:
        """Get executed trades"""
        return self.trades
