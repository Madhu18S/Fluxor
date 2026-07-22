"""
State space representation for RL execution optimization
Encodes market microstructure into learnable state vectors
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
from datetime import datetime
import logging

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ExecutionState:
    """
    Represents current market/execution state for RL agent
    """
    # Spread information
    bid_ask_spreads: Dict[str, float]  # {venue: spread_bps}
    mid_prices: Dict[str, float]  # {venue: price}
    
    # Volume information
    order_book_imbalance: Dict[str, float]  # {venue: bid_vol / (bid_vol + ask_vol)}
    remaining_quantity: float  # Quantity left to execute
    
    # Position information
    current_position: float
    unrealized_pnl: float
    time_to_expiry: float  # Seconds until urgency increases
    
    # Market microstructure
    volatility: float  # Realized volatility (in %)
    trend: float  # Price momentum (-1 to 1)
    venue_latencies: Dict[str, float]  # {venue: latency_ms}
    
    def to_vector(self, normalize: bool = True) -> np.ndarray:
        """
        Convert state to normalized feature vector for neural network
        """
        features = []
        
        # Spread features (normalized to 0-1)
        avg_spread = np.mean(list(self.bid_ask_spreads.values())) if self.bid_ask_spreads else 0
        features.append(min(avg_spread / 100, 1.0))  # Cap at 100 bps
        
        # Imbalance features
        avg_imbalance = np.mean(list(self.order_book_imbalance.values())) if self.order_book_imbalance else 0.5
        features.append(avg_imbalance)
        
        # Quantity features
        features.append(min(self.remaining_quantity / 1000, 1.0))  # Normalize to 1000 units max
        
        # Position and PnL
        features.append(np.tanh(self.current_position / 100))  # Bounded
        features.append(np.tanh(self.unrealized_pnl / 10000))  # Bounded
        
        # Time urgency
        time_urgency = 1.0 - np.exp(-self.time_to_expiry / 60)  # Increases over time
        features.append(min(time_urgency, 1.0))
        
        # Market conditions
        features.append(min(self.volatility / 50, 1.0))  # Normalize volatility
        features.append(np.tanh(self.trend))  # Already bounded
        
        # Latency features
        avg_latency = np.mean(list(self.venue_latencies.values())) if self.venue_latencies else 50
        features.append(min(avg_latency / 500, 1.0))  # Normalize to 500ms max
        
        features_array = np.array(features, dtype=np.float32)
        
        if normalize:
            # Ensure all features are bounded [0, 1]
            features_array = np.clip(features_array, 0, 1)
        
        return features_array


class StateSpace:
    """
    Manages state space for execution RL problem
    Continuous state space with discrete action space
    """
    
    def __init__(
        self,
        venues: List[str],
        max_position: float = 100.0,
        max_quantity: float = 1000.0,
    ):
        self.venues = venues
        self.max_position = max_position
        self.max_quantity = max_quantity
        
        # State dimensions
        self.state_dim = 9  # Number of features in state vector
        
        # Action space
        self.num_actions = len(venues) * 3  # venue * (aggressive, patient, wait)
    
    @property
    def action_names(self) -> List[str]:
        """
        Get human-readable action names
        """
        actions = []
        for venue in self.venues:
            actions.extend([
                f"{venue}_aggressive",
                f"{venue}_patient",
                f"{venue}_wait",
            ])
        return actions
    
    def decode_action(self, action_idx: int) -> Tuple[str, str]:
        """
        Decode action index to (venue, execution_type)
        """
        venue_idx = action_idx // 3
        exec_type_idx = action_idx % 3
        
        venue = self.venues[venue_idx]
        exec_types = ["aggressive", "patient", "wait"]
        exec_type = exec_types[exec_type_idx]
        
        return venue, exec_type
    
    def encode_action(self, venue: str, exec_type: str) -> int:
        """
        Encode (venue, execution_type) to action index
        """
        venue_idx = self.venues.index(venue)
        exec_types = ["aggressive", "patient", "wait"]
        exec_type_idx = exec_types.index(exec_type)
        
        return venue_idx * 3 + exec_type_idx
    
    def is_terminal(self, state: ExecutionState) -> bool:
        """
        Check if state is terminal (execution complete)
        """
        return state.remaining_quantity <= 0 or state.time_to_expiry <= 0
    
    def get_state_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get min and max bounds for state features
        """
        lower = np.zeros(self.state_dim, dtype=np.float32)
        upper = np.ones(self.state_dim, dtype=np.float32)
        return lower, upper
