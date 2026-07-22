"""
Smart Order Router (SOR) - Optimal execution path selection
Uses learned policies to route orders across venues minimizing cost
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from src.utils.logger import setup_logger
from src.rl.state_space import ExecutionState, StateSpace
from src.rl.q_learning import QLearningExecutor

logger = setup_logger(__name__)


@dataclass
class ExecutionPlan:
    """Execution plan with venue and timing"""
    venue: str
    execution_type: str  # aggressive, patient, wait
    quantity: float
    limit_price: Optional[float] = None
    timestamp: datetime = None
    expected_cost: float = 0.0
    expected_time: float = 0.0


class SmartOrderRouter:
    """
    Routes orders across venues using learned optimal policies
    Minimizes execution cost and market impact
    """
    
    def __init__(
        self,
        q_executor: QLearningExecutor,
        state_space: StateSpace,
        venues: List[str],
    ):
        self.q_executor = q_executor
        self.state_space = state_space
        self.venues = venues
        
        # Routing history
        self.routing_history: List[ExecutionPlan] = []
        
        # Performance metrics
        self.total_executed = 0.0
        self.total_cost = 0.0
    
    def route_order(
        self,
        state: ExecutionState,
        quantity: float,
        side: str = "buy",
    ) -> ExecutionPlan:
        """
        Route order using learned policy
        
        Args:
            state: Current market state
            quantity: Order quantity to execute
            side: buy or sell
        
        Returns:
            ExecutionPlan with venue and execution parameters
        """
        # Get best action from Q-learning agent
        action, venue, exec_type = self.q_executor.select_best_action(state)
        
        logger.info(f"SOR: Route {quantity} {side} to {venue} ({exec_type})")
        
        # Calculate execution parameters
        plan = self._create_execution_plan(
            state=state,
            venue=venue,
            execution_type=exec_type,
            quantity=quantity,
            side=side,
        )
        
        self.routing_history.append(plan)
        return plan
    
    def _create_execution_plan(
        self,
        state: ExecutionState,
        venue: str,
        execution_type: str,
        quantity: float,
        side: str,
    ) -> ExecutionPlan:
        """
        Create detailed execution plan
        """
        # Get prices
        mid_price = state.mid_prices.get(venue, 0)
        spread_bps = state.bid_ask_spreads.get(venue, 10)
        
        if side == "buy":
            # Buy side: pay ask
            limit_price = mid_price * (1 + spread_bps / 10000)
            # Aggressive: immediate execution, Patient: limit order
            if execution_type == "aggressive":
                limit_price *= 1.002  # Slightly aggressive
            elif execution_type == "patient":
                limit_price *= 0.999  # Slightly passive
        else:
            # Sell side: receive bid
            limit_price = mid_price * (1 - spread_bps / 10000)
            if execution_type == "aggressive":
                limit_price *= 0.998  # Slightly aggressive
            elif execution_type == "patient":
                limit_price *= 1.001  # Slightly passive
        
        # Estimate costs
        expected_cost = self._estimate_cost(
            quantity=quantity,
            price=limit_price,
            spread_bps=spread_bps,
            exec_type=execution_type,
        )
        
        # Estimate execution time
        expected_time = self._estimate_execution_time(execution_type)
        
        plan = ExecutionPlan(
            venue=venue,
            execution_type=execution_type,
            quantity=quantity,
            limit_price=limit_price,
            timestamp=datetime.utcnow(),
            expected_cost=expected_cost,
            expected_time=expected_time,
        )
        
        return plan
    
    def _estimate_cost(
        self,
        quantity: float,
        price: float,
        spread_bps: float,
        exec_type: str,
    ) -> float:
        """
        Estimate execution cost in basis points
        """
        # Half-spread cost
        cost = spread_bps / 2
        
        # Market impact (square-root model)
        size_millions = quantity / 1_000_000
        impact_bps = 0.5 * np.sqrt(size_millions)  # Simplified
        
        if exec_type == "aggressive":
            cost += impact_bps * 1.5  # More aggressive, higher impact
        elif exec_type == "patient":
            cost += impact_bps * 0.5  # Patient, lower impact
        # wait has minimal impact
        
        return cost
    
    def _estimate_execution_time(self, exec_type: str) -> float:
        """
        Estimate execution time in seconds
        """
        if exec_type == "aggressive":
            return 1.0  # Immediate
        elif exec_type == "patient":
            return 30.0  # Patient limit order
        else:  # wait
            return 60.0  # Wait for better prices
    
    def route_split_order(
        self,
        state: ExecutionState,
        quantity: float,
        num_splits: int = 3,
        side: str = "buy",
    ) -> List[ExecutionPlan]:
        """
        Route order split across multiple venues
        Uses RL to optimize split allocation
        """
        logger.info(f"SOR: Split-routing {quantity} across {num_splits} venues")
        
        plans = []
        qty_per_split = quantity / num_splits
        
        for i in range(num_splits):
            plan = self.route_order(
                state=state,
                quantity=qty_per_split,
                side=side,
            )
            plans.append(plan)
            
            # Slightly adjust state for next split
            state.remaining_quantity -= qty_per_split
        
        return plans
    
    def get_routing_metrics(self) -> Dict:
        """
        Get routing performance metrics
        """
        if not self.routing_history:
            return {}
        
        total_planned_cost = sum(plan.expected_cost for plan in self.routing_history)
        avg_cost = np.mean([plan.expected_cost for plan in self.routing_history])
        
        return {
            "total_routes": len(self.routing_history),
            "total_quantity": sum(plan.quantity for plan in self.routing_history),
            "avg_cost_bps": avg_cost,
            "total_planned_cost_bps": total_planned_cost,
            "venues_used": list(set(plan.venue for plan in self.routing_history)),
        }
