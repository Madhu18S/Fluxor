"""
End-to-end backtest runner orchestration
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import yaml

from src.utils.logger import setup_logger
from src.backtesting.simulator import BacktestSimulator, BacktestBar
from src.backtesting.friction_layer import FrictionConfig
from src.backtesting.metrics import BacktestMetrics
from src.core.opportunity_scanner import OpportunityScanner
from src.core.executor import Executor

logger = setup_logger(__name__)


class BacktestRunner:
    """
    Orchestrates complete backtest workflow
    Handles config loading, simulation, and reporting
    """
    
    def __init__(
        self,
        strategy_name: str = "triangular_arbitrage",
        start_date: str = "2024-01-01",
        end_date: str = "2024-12-31",
        initial_capital: float = 10000.0,
    ):
        self.strategy_name = strategy_name
        self.start_date = datetime.fromisoformat(start_date)
        self.end_date = datetime.fromisoformat(end_date)
        self.initial_capital = initial_capital
        
        # Components
        self.simulator: Optional[BacktestSimulator] = None
        self.scanner: Optional[OpportunityScanner] = None
        self.executor: Optional[Executor] = None
        self.metrics: Optional[BacktestMetrics] = None
    
    def load_historical_data(self, data_source: str = "mock") -> List[BacktestBar]:
        """
        Load historical market data
        """
        logger.info(f"Loading historical data from {data_source}")
        
        if data_source == "mock":
            return self._generate_mock_data()
        else:
            # Would load from database or CSV
            return []
    
    def _generate_mock_data(self) -> List[BacktestBar]:
        """
        Generate mock OHLCV data for testing
        """
        bars = []
        current_price = 50000
        current_date = self.start_date
        venues = ["binance", "kraken", "uniswap_v3"]
        symbols = ["BTC/USD", "ETH/USD"]
        
        while current_date <= self.end_date:
            for venue in venues:
                for symbol in symbols:
                    # Generate random price movement
                    daily_change = np.random.uniform(-0.02, 0.02)
                    open_price = current_price * (1 + daily_change)
                    high_price = open_price * (1 + abs(daily_change))
                    low_price = open_price * (1 - abs(daily_change))
                    close_price = low_price + (high_price - low_price) * np.random.random()
                    volume = np.random.uniform(100, 1000)
                    
                    bar = BacktestBar(
                        timestamp=current_date,
                        venue=venue,
                        symbol=symbol,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                    )
                    bars.append(bar)
            
            current_date += timedelta(days=1)
            current_price = close_price
        
        logger.info(f"Generated {len(bars)} mock bars")
        return bars
    
    def initialize(self) -> None:
        """
        Initialize backtest components
        """
        logger.info(f"Initializing backtest: {self.strategy_name}")
        
        # Create friction config
        friction_config = FrictionConfig(
            latency_mean_ms=50.0,
            maker_fee_bps=2.0,
            taker_fee_bps=5.0,
        )
        
        # Initialize components
        self.simulator = BacktestSimulator(
            initial_capital=self.initial_capital,
            friction_config=friction_config,
        )
        
        self.scanner = OpportunityScanner(
            min_spread=0.002,
            max_spread=0.015,
            min_volume=10.0,
        )
        
        self.executor = Executor(
            max_position_size=self.initial_capital * 0.1,
            timeout_seconds=30.0,
        )
    
    async def run(self) -> BacktestMetrics:
        """
        Execute complete backtest
        """
        logger.info("\n" + "="*60)
        logger.info(f"Running backtest: {self.strategy_name}")
        logger.info(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        logger.info(f"Initial capital: ${self.initial_capital:,.2f}")
        logger.info("="*60 + "\n")
        
        try:
            # Initialize
            self.initialize()
            
            # Load data
            bars = self.load_historical_data()
            if not bars:
                logger.error("No historical data loaded")
                return None
            
            self.simulator.load_historical_data(bars)
            
            # Run simulation
            self.metrics = await self.simulator.run_backtest(
                scanner=self.scanner,
                executor=self.executor,
            )
            
            # Print results
            logger.info("\n" + str(self.metrics))
            
            return self.metrics
        
        except Exception as e:
            logger.error(f"Backtest failed: {e}", exc_info=True)
            return None
    
    def export_results(self, filepath: str) -> None:
        """
        Export backtest results to JSON
        """
        if not self.metrics:
            logger.warning("No metrics to export")
            return
        
        import json
        
        results = {
            "strategy": self.strategy_name,
            "period": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat(),
            },
            "metrics": self.metrics.to_dict(),
            "trades": len(self.simulator.trades),
        }
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results exported to {filepath}")


# Import numpy for mock data generation
import numpy as np
