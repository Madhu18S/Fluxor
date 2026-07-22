# Fluxor - Example Scripts

## Example 1: Basic Opportunity Scanner

```python
# examples/01_basic_scan.py
import asyncio
from src.core.price_feed import PriceFeed, PriceSnapshot
from src.core.opportunity_scanner import OpportunityScanner
from datetime import datetime

async def main():
    """
    Basic example: Scan for arbitrage opportunities
    """
    print("\n🚀 Fluxor - Basic Arbitrage Scanner\n")
    
    # Create scanner
    scanner = OpportunityScanner(
        min_spread=0.002,  # 0.2% minimum spread
        max_spread=0.05,   # 5% maximum (filter out outliers)
        min_volume=10.0,   # Minimum volume USD
        fee_bps=7.0        # Total fees in basis points
    )
    
    # Mock price data from 3 venues
    prices = {
        "binance": {
            "BTC/USD": PriceSnapshot(
                timestamp=datetime.utcnow(),
                venue="binance",
                symbol="BTC/USD",
                bid=49999,
                ask=50001,
                mid=50000,
                volume=100
            ),
            "ETH/USD": PriceSnapshot(
                timestamp=datetime.utcnow(),
                venue="binance",
                symbol="ETH/USD",
                bid=2999,
                ask=3001,
                mid=3000,
                volume=500
            ),
        },
        "kraken": {
            "BTC/USD": PriceSnapshot(
                timestamp=datetime.utcnow(),
                venue="kraken",
                symbol="BTC/USD",
                bid=50005,      # Better bid
                ask=50015,
                mid=50010,
                volume=80
            ),
            "ETH/USD": PriceSnapshot(
                timestamp=datetime.utcnow(),
                venue="kraken",
                symbol="ETH/USD",
                bid=3005,
                ask=3010,
                mid=3007.5,
                volume=400
            ),
        },
    }
    
    # Scan for opportunities
    print("Scanning for opportunities...\n")
    opportunities = await scanner.scan(prices)
    
    if not opportunities:
        print("❌ No profitable opportunities found")
        return
    
    # Display results
    print(f"✅ Found {len(opportunities)} opportunities!\n")
    
    for i, opp in enumerate(opportunities[:5], 1):
        print(f"Opportunity #{i}")
        print(f"  Symbol: {opp.symbol}")
        print(f"  Type: {opp.opportunity_type}")
        print(f"  Spread: {opp.spread*100:.4f}%")
        print(f"  Gross profit (bps): {opp.spread*10000:.2f}")
        print(f"  Net profit (bps): {opp.net_profit_bps:.2f}")
        print(f"  Entry price: ${opp.entry_price:,.2f}")
        print(f"  Exit price: ${opp.exit_price:,.2f}")
        print(f"  Path: {opp.path}")
        print()
    
    # Statistics
    stats = scanner.get_statistics()
    print("Statistics:")
    print(f"  Total opportunities: {stats['total_opportunities']}")
    print(f"  Profitable: {stats['profitable']}")
    print(f"  Avg spread: {stats['avg_spread_bps']:.2f} bps")
    print(f"  Max spread: {stats['max_spread_bps']:.2f} bps")
    print(f"  Cross-exchange: {stats['by_type']['cross_exchange']}")
    print(f"  Triangular: {stats['by_type']['triangular']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 2: Backtest Historical Data

```python
# examples/02_backtest.py
import asyncio
from src.backtesting.backtest_runner import BacktestRunner

async def main():
    """
    Backtest example: Test strategy on historical data
    """
    print("\n📊 Fluxor - Backtest Runner\n")
    
    # Create runner
    runner = BacktestRunner(
        strategy_name="triangular_arbitrage",
        start_date="2024-01-01",
        end_date="2024-03-31",
        initial_capital=10000.0,
    )
    
    print("Starting backtest...")
    print(f"Strategy: {runner.strategy_name}")
    print(f"Period: {runner.start_date.date()} to {runner.end_date.date()}")
    print(f"Capital: ${runner.initial_capital:,.2f}\n")
    
    # Run backtest
    metrics = await runner.run()
    
    if not metrics:
        print("❌ Backtest failed")
        return
    
    # Show results
    print(metrics)  # Uses __str__ method for pretty output
    
    # Export to JSON
    runner.export_results("backtest_results.json")
    print("✅ Results exported to backtest_results.json")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 3: Train Q-Learning Agent

```python
# examples/03_train_rl.py
import asyncio
from src.rl.q_learning import QLearningExecutor
from src.rl.env import ArbitrageEnvironment

async def main():
    """
    RL training example: Train Q-Learning agent
    """
    print("\n🧠 Fluxor - Q-Learning Training\n")
    
    # Create environment
    env = ArbitrageEnvironment(
        venues=["binance", "kraken", "uniswap_v3"],
        initial_quantity=100.0,
        max_time=300.0,  # 5 minutes
    )
    
    print(f"Environment:")
    print(f"  Venues: {env.venues}")
    print(f"  State dimension: {env.state_space.state_dim}")
    print(f"  Action space: {env.state_space.num_actions}")
    print(f"  Actions: {env.state_space.action_names}\n")
    
    # Create Q-Learning agent
    agent = QLearningExecutor(
        state_space=env.state_space,
        learning_rate=0.1,
        discount_factor=0.99,
        epsilon=0.1,
        epsilon_decay=0.995,
    )
    
    print("Training agent...\n")
    
    # Train
    agent.train(env, episodes=500, max_steps=100)
    
    # Show statistics
    stats = agent.get_statistics()
    print(f"\nTraining Complete!")
    print(f"  Episodes: {stats['total_episodes']}")
    print(f"  Total reward: {stats['total_reward']:.2f}")
    print(f"  Avg reward: {stats['avg_reward']:.2f}")
    print(f"  Max reward: {stats['max_reward']:.2f}")
    print(f"  Q-table states: {stats['q_table_size']}")
    
    # Save model
    agent.save_model("q_learning_model.pkl")
    print("✅ Model saved to q_learning_model.pkl")
    
    # Test agent
    print("\nTesting trained agent...")
    state = env.reset()
    total_reward = 0
    
    for step in range(50):
        action, venue, exec_type = agent.select_best_action(state)
        next_state, reward, done, info = env.step(action)
        
        total_reward += reward
        state = next_state
        
        if step % 10 == 0:
            print(f"  Step {step}: Executed {info['executed']:.2f} qty, Cost {info['cost_bps']:.2f} bps")
        
        if done:
            break
    
    print(f"\nTest Result: Total reward = {total_reward:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Example 4: Trade Execution

```python
# examples/04_execute_trade.py
import asyncio
from src.core.opportunity_scanner import ArbitrageOpportunity
from src.core.executor import Executor
from datetime import datetime

async def main():
    """
    Execution example: Execute detected opportunity
    """
    print("\n⚡ Fluxor - Trade Executor\n")
    
    # Create executor
    executor = Executor(
        max_position_size=1000.0,
        timeout_seconds=30.0,
        partial_fill_allowed=True,
    )
    
    # Create mock opportunity
    opportunity = ArbitrageOpportunity(
        opportunity_type="cross_exchange",
        symbol="BTC/USD",
        path=[("binance", "BTC/USD"), ("kraken", "BTC/USD")],
        spread=0.002,  # 0.2%
        entry_price=50000,
        exit_price=50010,
        timestamp=datetime.utcnow(),
        estimated_volume=1.0,
        fees_bps=7.0,
    )
    
    print(f"Opportunity:")
    print(f"  Type: {opportunity.opportunity_type}")
    print(f"  Symbol: {opportunity.symbol}")
    print(f"  Spread: {opportunity.spread*100:.4f}%")
    print(f"  Net profit: {opportunity.net_profit_bps:.2f} bps")
    print(f"  Path: {opportunity.path}\n")
    
    # Execute
    print("Executing...")
    trade = await executor.execute_opportunity(opportunity)
    
    if not trade:
        print("❌ Execution failed")
        return
    
    # Show results
    print(f"\n✅ Trade Executed!")
    print(f"  Trade ID: {trade.trade_id}")
    print(f"  Status: {trade.status}")
    print(f"  P&L: ${trade.pnl:,.2f}")
    print(f"  P&L (bps): {trade.pnl_bps:.2f}")
    print(f"  Orders: {len(trade.orders)}")
    
    # Show orders
    for i, order in enumerate(trade.orders, 1):
        print(f"\n  Order #{i}:")
        print(f"    Venue: {order.venue}")
        print(f"    Side: {order.side}")
        print(f"    Qty: {order.quantity}")
        print(f"    Price: ${order.price:,.2f}")
        print(f"    Status: {order.status}")
    
    # Performance metrics
    metrics = executor.get_performance_metrics()
    print(f"\nExecutor Performance:")
    print(f"  Total trades: {metrics['total_trades']}")
    print(f"  Successful: {metrics['successful_trades']}")
    print(f"  Total P&L: ${metrics['total_pnl']:,.2f}")
    print(f"  Win rate: {metrics['win_rate']*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
```

## How to Run Examples

```bash
# Install fluxor first
pip install -e .

# Run individual examples
python examples/01_basic_scan.py
python examples/02_backtest.py
python examples/03_train_rl.py
python examples/04_execute_trade.py

# Or run all
for f in examples/*.py; do python "$f"; done
```
