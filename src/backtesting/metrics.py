"""
Backtesting metrics and performance analysis
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime, timedelta
import logging

from src.utils.logger import setup_logger
from src.utils.metrics import PerformanceMetrics, MetricsCalculator

logger = setup_logger(__name__)


@dataclass
class BacktestMetrics(PerformanceMetrics):
    """Extended metrics specific to backtesting"""
    
    # Additional backtesting metrics
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trading_days: int = 0
    longest_winning_streak: int = 0
    longest_losing_streak: int = 0
    
    # Drawdown tracking
    cumulative_returns: List[float] = field(default_factory=list)
    peak_value: float = 0
    trough_value: float = 0
    
    @property
    def duration_days(self) -> int:
        """Number of days in backtest period"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    @property
    def annual_return(self) -> float:
        """Annualized return"""
        if self.duration_days == 0:
            return 0
        years = self.duration_days / 365.25
        return (self.total_pnl / years) if years > 0 else 0
    
    @property
    def annual_volatility(self) -> float:
        """Annualized volatility"""
        if len(self.returns) < 2:
            return 0
        return np.std(self.returns) * np.sqrt(252)
    
    @property
    def sortino_ratio(self) -> float:
        """Sortino ratio (downside deviation)"""
        if len(self.returns) < 2:
            return 0
        
        returns_array = np.array(self.returns)
        downside = returns_array[returns_array < 0]
        
        if len(downside) == 0:
            return 0
        
        downside_std = np.std(downside)
        if downside_std == 0:
            return 0
        
        return np.mean(returns_array) / downside_std * np.sqrt(252)
    
    @property
    def information_ratio(self) -> float:
        """Information ratio (return per unit of tracking error)"""
        if len(self.returns) < 2:
            return 0
        
        returns_array = np.array(self.returns)
        tracking_error = np.std(returns_array)
        
        if tracking_error == 0:
            return 0
        
        return np.mean(returns_array) / tracking_error
    
    @property
    def consecutive_winners(self) -> int:
        """Longest winning streak"""
        return self.longest_winning_streak
    
    @property
    def consecutive_losers(self) -> int:
        """Longest losing streak"""
        return self.longest_losing_streak
    
    def update_streaks(self, pnl: float) -> None:
        """Update winning/losing streaks"""
        # This would be called after each trade
        pass
    
    def update_drawdown(self, current_value: float) -> None:
        """Update peak and trough for drawdown calculation"""
        if current_value > self.peak_value:
            self.peak_value = current_value
        
        if current_value < self.trough_value or self.trough_value == 0:
            self.trough_value = current_value
    
    def to_dict(self) -> Dict:
        """Export all metrics as dictionary"""
        base_dict = super().to_dict()
        
        extended_dict = {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "duration_days": self.duration_days,
            "annual_return": self.annual_return,
            "annual_volatility": self.annual_volatility,
            "sortino_ratio": self.sortino_ratio,
            "information_ratio": self.information_ratio,
            "longest_win_streak": self.longest_winning_streak,
            "longest_loss_streak": self.longest_losing_streak,
        }
        
        return {**base_dict, **extended_dict}
    
    def __str__(self) -> str:
        """Pretty print extended metrics"""
        return f"""
╔════════════════════════════════════════════════════════════╗
║              Backtest Performance Report                   ║
╠════════════════════════════════════════════════════════════╣
║ Period: {self.start_date.strftime('%Y-%m-%d') if self.start_date else 'N/A'} to {self.end_date.strftime('%Y-%m-%d') if self.end_date else 'N/A':<21} ║
║ Duration: {self.duration_days:>49} days ║
╠════════════════════════════════════════════════════════════╣
║ Total Trades: {self.total_trades:>43} ║
║ Win Rate: {self.win_rate*100:>49.2f}% ║
║ Longest Win Streak: {self.longest_winning_streak:>38} ║
║ Longest Loss Streak: {self.longest_losing_streak:>37} ║
╠════════════════════════════════════════════════════════════╣
║ Total P&L: ${self.total_pnl:>47,.2f} ║
║ Annual Return: {self.annual_return:>43.2f}% ║
║ Volatility (Annual): {self.annual_volatility:>39.2f}% ║
║ Total Fees: ${self.total_fees:>47,.2f} ║
╠════════════════════════════════════════════════════════════╣
║ Sharpe Ratio: {self.sharpe_ratio:>46.2f} ║
║ Sortino Ratio: {self.sortino_ratio:>45.2f} ║
║ Information Ratio: {self.information_ratio:>41.2f} ║
║ Max Drawdown: {self.max_drawdown*100:>46.2f}% ║
║ Recovery Factor: {self.recovery_factor:>42.2f} ║
║ Calmar Ratio: {self.calmar_ratio:>47.2f} ║
╚════════════════════════════════════════════════════════════╝
        """
