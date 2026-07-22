"""
Performance metrics and statistics calculation
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime, timedelta


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for trading strategies"""
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0
    total_fees: float = 0
    
    # Statistical metrics
    returns: List[float] = field(default_factory=list)
    drawdowns: List[float] = field(default_factory=list)
    
    @property
    def win_rate(self) -> float:
        """Win rate percentage"""
        if self.total_trades == 0:
            return 0
        return self.winning_trades / self.total_trades
    
    @property
    def avg_win(self) -> float:
        """Average winning trade size"""
        if self.winning_trades == 0:
            return 0
        return self.total_pnl / self.winning_trades
    
    @property
    def avg_loss(self) -> float:
        """Average losing trade size"""
        if self.losing_trades == 0:
            return 0
        return self.total_pnl / self.losing_trades
    
    @property
    def profit_factor(self) -> float:
        """Profit factor (gross profit / gross loss)"""
        if self.total_pnl <= 0:
            return 0
        # Simplified: assumes positive trades = wins, negative = losses
        return max(abs(r) for r in self.returns) / max(abs(r) for r in self.returns) if self.returns else 0
    
    @property
    def sharpe_ratio(self) -> float:
        """Sharpe ratio (risk-adjusted return)"""
        if not self.returns:
            return 0
        returns_array = np.array(self.returns)
        if np.std(returns_array) == 0:
            return 0
        # Annualization factor for trading (assuming ~250 trading days)
        return np.mean(returns_array) / np.std(returns_array) * np.sqrt(250)
    
    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown"""
        if not self.drawdowns:
            return 0
        return max(self.drawdowns)
    
    @property
    def recovery_factor(self) -> float:
        """Recovery factor (net profit / max drawdown)"""
        if self.max_drawdown == 0:
            return 0
        return self.total_pnl / self.max_drawdown
    
    @property
    def calmar_ratio(self) -> float:
        """Calmar ratio (annualized return / max drawdown)"""
        if self.max_drawdown == 0:
            return 0
        annual_return = (self.total_pnl / 252) if self.total_trades > 0 else 0
        return annual_return / self.max_drawdown
    
    def add_trade(self, pnl: float, fees: float = 0) -> None:
        """Add a trade result"""
        self.total_trades += 1
        net_pnl = pnl - fees
        self.total_pnl += net_pnl
        self.total_fees += fees
        self.returns.append(net_pnl)
        
        if net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
    
    def add_drawdown(self, drawdown: float) -> None:
        """Track drawdown"""
        self.drawdowns.append(drawdown)
    
    def to_dict(self) -> Dict:
        """Export metrics as dictionary"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "total_fees": self.total_fees,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "recovery_factor": self.recovery_factor,
            "calmar_ratio": self.calmar_ratio,
        }
    
    def __str__(self) -> str:
        """Pretty print metrics"""
        return f"""
╔════════════════════════════════════════╗
║        Trading Performance Report      ║
╠════════════════════════════════════════╣
║ Total Trades:          {self.total_trades:>15} ║
║ Win Rate:              {self.win_rate*100:>14.2f}% ║
║ Total P&L:             ${self.total_pnl:>14.2f} ║
║ Total Fees:            ${self.total_fees:>14.2f} ║
║ Sharpe Ratio:          {self.sharpe_ratio:>15.2f} ║
║ Max Drawdown:          {self.max_drawdown*100:>14.2f}% ║
║ Recovery Factor:       {self.recovery_factor:>15.2f} ║
║ Calmar Ratio:          {self.calmar_ratio:>15.2f} ║
╚════════════════════════════════════════╝
        """


class MetricsCalculator:
    """Helper class for calculating various metrics"""
    
    @staticmethod
    def calculate_roi(initial_capital: float, final_capital: float) -> float:
        """Calculate return on investment"""
        if initial_capital == 0:
            return 0
        return (final_capital - initial_capital) / initial_capital
    
    @staticmethod
    def calculate_volatility(returns: List[float]) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0
        return np.std(returns) * np.sqrt(252)
    
    @staticmethod
    def calculate_drawdown_series(values: List[float]) -> List[float]:
        """Calculate running drawdown series"""
        cummax = np.maximum.accumulate(values)
        drawdown = (np.array(values) - cummax) / cummax
        return drawdown.tolist()
    
    @staticmethod
    def calculate_correlation(returns1: List[float], returns2: List[float]) -> float:
        """Calculate correlation between two return series"""
        if len(returns1) < 2 or len(returns2) < 2:
            return 0
        return np.corrcoef(returns1, returns2)[0, 1]
    
    @staticmethod
    def calculate_var(returns: List[float], confidence: float = 0.95) -> float:
        """Calculate Value at Risk (VaR)"""
        if len(returns) == 0:
            return 0
        return np.percentile(returns, (1 - confidence) * 100)
    
    @staticmethod
    def calculate_cvar(returns: List[float], confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (CVaR)"""
        if len(returns) == 0:
            return 0
        var = MetricsCalculator.calculate_var(returns, confidence)
        return np.mean([r for r in returns if r <= var])
