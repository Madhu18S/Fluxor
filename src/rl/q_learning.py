"""
Q-Learning algorithm for optimal execution
Learn value functions for order routing and execution timing
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import logging

from src.utils.logger import setup_logger
from src.rl.state_space import StateSpace, ExecutionState

logger = setup_logger(__name__)


class QLearningExecutor:
    """
    Q-Learning agent for execution optimization
    Learns to minimize market impact and execution costs
    """
    
    def __init__(
        self,
        state_space: StateSpace,
        learning_rate: float = 0.1,
        discount_factor: float = 0.99,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.995,
    ):
        self.state_space = state_space
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        
        # Q-table: discretized state -> action -> value
        self.q_table: Dict[str, np.ndarray] = defaultdict(
            lambda: np.zeros(state_space.num_actions)
        )
        
        # Experience tracking
        self.episode_rewards: List[float] = []
        self.training_episodes = 0
    
    def discretize_state(self, state: ExecutionState) -> str:
        """
        Discretize continuous state to Q-table key
        Bins each feature into 5 levels (0-4)
        """
        state_vector = state.to_vector(normalize=True)
        
        # Bin each feature into 5 levels
        bins = np.digitize(state_vector, bins=[0.2, 0.4, 0.6, 0.8])
        
        # Convert to string key
        key = "-".join(map(str, bins))
        return key
    
    def select_action(self, state: ExecutionState, training: bool = True) -> int:
        """
        Select action using epsilon-greedy policy
        """
        state_key = self.discretize_state(state)
        q_values = self.q_table[state_key]
        
        if training and np.random.random() < self.epsilon:
            # Explore: random action
            return np.random.randint(self.state_space.num_actions)
        else:
            # Exploit: best action
            return np.argmax(q_values)
    
    def update(
        self,
        state: ExecutionState,
        action: int,
        reward: float,
        next_state: ExecutionState,
        done: bool,
    ) -> None:
        """
        Update Q-value using Q-learning update rule
        Q(s,a) = Q(s,a) + α[r + γ*max(Q(s',a')) - Q(s,a)]
        """
        state_key = self.discretize_state(state)
        next_state_key = self.discretize_state(next_state)
        
        current_q = self.q_table[state_key][action]
        max_next_q = np.max(self.q_table[next_state_key]) if not done else 0
        
        # Q-learning update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state_key][action] = new_q
    
    def train(
        self,
        env: 'ArbitrageEnvironment',
        episodes: int = 1000,
        max_steps: int = 100,
    ) -> None:
        """
        Train agent on environment
        """
        logger.info(f"Starting Q-Learning training for {episodes} episodes")
        
        for episode in range(episodes):
            state = env.reset()
            episode_reward = 0
            
            for step in range(max_steps):
                # Select and execute action
                action = self.select_action(state, training=True)
                next_state, reward, done, info = env.step(action)
                
                # Update Q-values
                self.update(state, action, reward, next_state, done)
                
                episode_reward += reward
                state = next_state
                
                if done:
                    break
            
            # Decay exploration
            self.epsilon *= self.epsilon_decay
            
            self.episode_rewards.append(episode_reward)
            self.training_episodes += 1
            
            if (episode + 1) % 100 == 0:
                avg_reward = np.mean(self.episode_rewards[-100:])
                logger.info(
                    f"Episode {episode + 1}/{episodes} | "
                    f"Avg Reward: {avg_reward:.2f} | "
                    f"Epsilon: {self.epsilon:.3f}"
                )
        
        logger.info("Training complete")
    
    def select_best_action(self, state: ExecutionState) -> Tuple[int, str, str]:
        """
        Select best action (greedy, no exploration)
        Returns action index and decoded (venue, exec_type)
        """
        action = self.select_action(state, training=False)
        venue, exec_type = self.state_space.decode_action(action)
        return action, venue, exec_type
    
    def get_action_distribution(self, state: ExecutionState) -> Dict[str, float]:
        """
        Get probability distribution over actions for current state
        """
        state_key = self.discretize_state(state)
        q_values = self.q_table[state_key]
        
        # Softmax distribution
        exp_q = np.exp(q_values - np.max(q_values))  # Numerical stability
        probs = exp_q / np.sum(exp_q)
        
        distribution = {}
        for action_idx, prob in enumerate(probs):
            action_name = self.state_space.action_names[action_idx]
            distribution[action_name] = float(prob)
        
        return distribution
    
    def get_statistics(self) -> Dict:
        """
        Get training statistics
        """
        if not self.episode_rewards:
            return {}
        
        rewards = np.array(self.episode_rewards)
        
        return {
            "total_episodes": self.training_episodes,
            "total_reward": float(np.sum(rewards)),
            "avg_reward": float(np.mean(rewards)),
            "max_reward": float(np.max(rewards)),
            "min_reward": float(np.min(rewards)),
            "q_table_size": len(self.q_table),
            "current_epsilon": self.epsilon,
        }
    
    def save_model(self, filepath: str) -> None:
        """
        Save Q-table to file
        """
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(self.q_table, f)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str) -> None:
        """
        Load Q-table from file
        """
        import pickle
        with open(filepath, 'rb') as f:
            self.q_table = pickle.load(f)
        logger.info(f"Model loaded from {filepath}")
