"""
Gym environment for execution RL training
Simulates order execution with market microstructure
"""

import numpy as np
from typing import Tuple, Dict, Optional
from datetime import datetime, timedelta
import logging

from src.utils.logger import setup_logger
from src.rl.state_space import ExecutionState, StateSpace

logger = setup_logger(__name__)


class ArbitrageEnvironment:
    """
    Gym-like environment for execution optimization
    Agent learns to minimize market impact and timing risk
    """
    
    def __init__(
        self,
        venues: list = None,
        initial_quantity: float = 100.0,
        max_time: float = 300.0,  # 5 minutes
        urgency_multiplier: float = 1.0,
    ):
        if venues is None:
            venues = ["binance", "kraken", "uniswap_v3"]
        
        self.venues = venues
        self.initial_quantity = initial_quantity
        self.max_time = max_time
        self.urgency_multiplier = urgency_multiplier
        
        # State space
        self.state_space = StateSpace(venues=venues)
        
        # Episode state
        self.current_state: Optional[ExecutionState] = None
        self.time_elapsed = 0.0
        self.executed_quantity = 0.0
        self.execution_cost = 0.0
        self.step_count = 0
    
    def reset(self) -> ExecutionState:
        """
        Reset environment to initial state
        """
        # Generate random initial market conditions
        bid_ask_spreads = {venue: np.random.uniform(5, 20) for venue in self.venues}
        mid_prices = {venue: 50000 + np.random.uniform(-1000, 1000) for venue in self.venues}
        imbalances = {venue: np.random.uniform(0.3, 0.7) for venue in self.venues}
        
        self.current_state = ExecutionState(
            bid_ask_spreads=bid_ask_spreads,
            mid_prices=mid_prices,
            order_book_imbalance=imbalances,
            remaining_quantity=self.initial_quantity,
            current_position=0.0,
            unrealized_pnl=0.0,
            time_to_expiry=self.max_time,
            volatility=np.random.uniform(0.5, 3.0),
            trend=np.random.uniform(-0.5, 0.5),
            venue_latencies={venue: np.random.uniform(20, 200) for venue in self.venues},
        )
        
        self.time_elapsed = 0.0
        self.executed_quantity = 0.0
        self.execution_cost = 0.0
        self.step_count = 0
        
        return self.current_state
    
    def step(self, action: int) -> Tuple[ExecutionState, float, bool, Dict]:
        """
        Execute one step of environment
        
        Returns:
            (next_state, reward, done, info)
        """
        self.step_count += 1
        
        # Decode action
        venue, exec_type = self.state_space.decode_action(action)
        
        # Execute on venue
        qty_executed, cost_bps = self._execute_order(venue, exec_type)
        
        # Update state
        self.executed_quantity += qty_executed
        self.execution_cost += cost_bps
        self.time_elapsed += self._get_execution_time(exec_type)
        
        # Update market conditions (random walk)
        self._update_market_state()
        
        # Calculate reward
        reward = self._calculate_reward(qty_executed, cost_bps)
        
        # Check if done
        done = (
            self.current_state.remaining_quantity <= 0 or
            self.current_state.time_to_expiry <= 0 or
            self.step_count >= 100
        )
        
        info = {
            "executed": qty_executed,
            "cost_bps": cost_bps,
            "venue": venue,
            "exec_type": exec_type,
            "total_executed": self.executed_quantity,
        }
        
        return self.current_state, reward, done, info
    
    def _execute_order(self, venue: str, exec_type: str) -> Tuple[float, float]:
        """
        Simulate order execution
        Returns (quantity_executed, cost_in_bps)
        """
        remaining = self.current_state.remaining_quantity
        
        # Execution depends on type
        if exec_type == "aggressive":
            qty_executed = remaining * 0.8  # Execute 80%
            cost_bps = 8.0  # Higher slippage
        elif exec_type == "patient":
            qty_executed = remaining * 0.3  # Execute 30%
            cost_bps = 3.0  # Lower slippage
        else:  # wait
            qty_executed = 0
            cost_bps = 0
        
        # Add venue-specific impact
        spread = self.current_state.bid_ask_spreads.get(venue, 10) / 2
        cost_bps += spread / 100
        
        return qty_executed, cost_bps
    
    def _get_execution_time(self, exec_type: str) -> float:
        """
        Time consumed by execution
        """
        if exec_type == "aggressive":
            return 1.0
        elif exec_type == "patient":
            return 30.0
        else:  # wait
            return 0.1
    
    def _update_market_state(self) -> None:
        """
        Update market state (random walk + urgency decay)
        """
        # Random price movements
        for venue in self.venues:
            price_shock = np.random.normal(0, 50)  # ±50 impact
            self.current_state.mid_prices[venue] += price_shock
            
            # Spread widens with volatility
            spread_shock = np.random.uniform(-2, 5)
            self.current_state.bid_ask_spreads[venue] = max(
                5, self.current_state.bid_ask_spreads[venue] + spread_shock
            )
        
        # Update urgency
        self.current_state.time_to_expiry = max(
            0, self.current_state.time_to_expiry - self._get_execution_time("patient")
        )
        self.current_state.remaining_quantity = max(
            0, self.initial_quantity - self.executed_quantity
        )
        
        # Trend update (mean reversion)
        self.current_state.trend *= 0.95  # Decay
        self.current_state.trend += np.random.normal(0, 0.05)
    
    def _calculate_reward(self, qty_executed: float, cost_bps: float) -> float:
        """
        Calculate reward signal
        Reward for execution, penalty for cost
        """
        # Reward for progress
        progress_reward = qty_executed / self.initial_quantity * 10
        
        # Penalty for cost
        cost_penalty = cost_bps / 100  # Normalize
        
        # Urgency bonus (reward completing early)
        urgency_bonus = (self.max_time - self.time_elapsed) / self.max_time
        
        # Total reward
        reward = progress_reward - cost_penalty + urgency_bonus * 0.5
        
        return reward
    
    def render(self, mode: str = "human") -> None:
        """
        Render current state
        """
        print(f"\n--- Step {self.step_count} ---")
        print(f"Time: {self.time_elapsed:.1f}s / {self.max_time:.1f}s")
        print(f"Executed: {self.executed_quantity:.2f} / {self.initial_quantity:.2f}")
        print(f"Cost: {self.execution_cost:.2f} bps")
        print(f"State vector: {self.current_state.to_vector()}")
