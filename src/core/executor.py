"""
Trade Execution Engine
Executes trades on detected arbitrage opportunities
"""

import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import uuid

from src.utils.logger import setup_logger
from src.core.opportunity_scanner import ArbitrageOpportunity

logger = setup_logger(__name__)


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """Represents a single order"""
    order_id: str
    venue: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0
    avg_fill_price: float = 0
    commission: float = 0
    error_msg: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]

    @property
    def fill_percentage(self) -> float:
        if self.quantity == 0:
            return 0
        return self.filled_qty / self.quantity


@dataclass
class Trade:
    """Represents a completed arbitrage trade"""
    trade_id: str
    opportunity: ArbitrageOpportunity
    orders: List[Order] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    pnl: float = 0
    pnl_bps: float = 0
    status: str = "active"  # active, completed, failed


class Executor:
    """
    Executes arbitrage trades with risk management
    Handles order placement, monitoring, and settlement
    """

    def __init__(
        self,
        max_position_size: float = 1000.0,
        timeout_seconds: float = 30.0,
        partial_fill_allowed: bool = True,
    ):
        self.max_position_size = max_position_size
        self.timeout_seconds = timeout_seconds
        self.partial_fill_allowed = partial_fill_allowed
        
        # Order and trade tracking
        self.orders: Dict[str, Order] = {}
        self.trades: Dict[str, Trade] = {}
        self.active_trades: List[Trade] = []

    async def execute_opportunity(self, opportunity: ArbitrageOpportunity) -> Optional[Trade]:
        """
        Execute an arbitrage opportunity
        Returns Trade object if successful, None otherwise
        """
        logger.info(f"Executing opportunity: {opportunity.symbol} | Spread: {opportunity.spread:.2%}")
        
        # Validate opportunity
        if not self._validate_opportunity(opportunity):
            logger.warning(f"Opportunity validation failed: {opportunity.symbol}")
            return None
        
        # Create trade
        trade_id = str(uuid.uuid4())
        trade = Trade(
            trade_id=trade_id,
            opportunity=opportunity,
        )
        
        try:
            # Build execution path
            orders = await self._build_execution_orders(opportunity)
            
            if not orders:
                logger.error("Failed to build execution orders")
                trade.status = "failed"
                return trade
            
            trade.orders = orders
            
            # Execute orders
            success = await self._execute_orders(orders)
            
            if success:
                # Calculate P&L
                trade.pnl = self._calculate_pnl(trade)
                trade.pnl_bps = (trade.pnl / opportunity.entry_price) * 10000
                trade.status = "completed"
                
                logger.info(
                    f"Trade executed: {trade_id} | "
                    f"P&L: ${trade.pnl:.2f} ({trade.pnl_bps:.2f} bps)"
                )
            else:
                trade.status = "failed"
                logger.error(f"Trade execution failed: {trade_id}")
            
        except Exception as e:
            logger.error(f"Error executing opportunity: {e}")
            trade.status = "failed"
        
        # Store trade
        self.trades[trade_id] = trade
        self.active_trades.append(trade)
        
        return trade

    async def _build_execution_orders(self, opportunity: ArbitrageOpportunity) -> List[Order]:
        """Build orders for executing the opportunity"""
        orders = []
        
        try:
            for i, (venue, symbol) in enumerate(opportunity.path):
                # Determine buy/sell
                if i == 0:
                    side = OrderSide.BUY
                    price = opportunity.entry_price
                elif i == len(opportunity.path) - 1:
                    side = OrderSide.SELL
                    price = opportunity.exit_price
                else:
                    # Intermediate leg
                    side = OrderSide.SELL if i % 2 == 1 else OrderSide.BUY
                    price = opportunity.entry_price  # Placeholder
                
                order = Order(
                    order_id=str(uuid.uuid4()),
                    venue=venue,
                    symbol=symbol,
                    side=side,
                    quantity=opportunity.estimated_volume,
                    price=price,
                    timestamp=datetime.utcnow(),
                )
                
                orders.append(order)
                self.orders[order.order_id] = order
            
            return orders
            
        except Exception as e:
            logger.error(f"Error building execution orders: {e}")
            return []

    async def _execute_orders(self, orders: List[Order]) -> bool:
        """Execute list of orders sequentially"""
        try:
            for order in orders:
                # In a real implementation, this would interface with venue APIs
                # For now, we simulate successful execution
                
                order.status = OrderStatus.SUBMITTED
                
                # Simulate order execution
                await asyncio.sleep(0.1)  # Simulate network latency
                
                # Update order status
                order.status = OrderStatus.FILLED
                order.filled_qty = order.quantity
                order.avg_fill_price = order.price
                
                logger.debug(f"Order executed: {order.order_id} on {order.venue}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing orders: {e}")
            return False

    def _calculate_pnl(self, trade: Trade) -> float:
        """Calculate profit/loss from executed trade"""
        try:
            buy_cost = 0
            sell_revenue = 0
            total_commission = 0
            
            for order in trade.orders:
                if order.side == OrderSide.BUY:
                    buy_cost += order.filled_qty * order.avg_fill_price
                else:
                    sell_revenue += order.filled_qty * order.avg_fill_price
                
                total_commission += order.commission
            
            pnl = sell_revenue - buy_cost - total_commission
            return pnl
            
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}")
            return 0

    def _validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate opportunity before execution"""
        # Check if profitable after fees
        if opportunity.net_profit_bps <= 0:
            logger.warning(f"Opportunity not profitable: {opportunity.net_profit_bps} bps")
            return False
        
        # Check position size
        if opportunity.estimated_volume > self.max_position_size:
            logger.warning(f"Position size exceeds limit: {opportunity.estimated_volume}")
            return False
        
        return True

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False
        
        order.status = OrderStatus.CANCELLED
        logger.info(f"Order cancelled: {order_id}")
        return True

    async def monitor_trade(self, trade: Trade) -> None:
        """Monitor an active trade"""
        start_time = datetime.utcnow()
        
        while trade.status == "active":
            # Check order statuses
            all_filled = all(order.status == OrderStatus.FILLED for order in trade.orders)
            any_failed = any(order.status == OrderStatus.FAILED for order in trade.orders)
            
            if all_filled:
                trade.status = "completed"
                break
            
            if any_failed:
                trade.status = "failed"
                break
            
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > self.timeout_seconds:
                logger.warning(f"Trade timeout: {trade.trade_id}")
                # Cancel remaining orders
                for order in trade.orders:
                    if order.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                        await self.cancel_order(order.order_id)
                trade.status = "failed"
                break
            
            await asyncio.sleep(0.5)

    def get_trade_history(self, limit: int = 100) -> List[Trade]:
        """Get recent trade history"""
        trades_list = list(self.trades.values())
        return sorted(
            trades_list,
            key=lambda t: t.timestamp,
            reverse=True
        )[:limit]

    def get_performance_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {
                "total_trades": 0,
                "successful_trades": 0,
                "total_pnl": 0,
                "avg_pnl": 0,
                "win_rate": 0,
            }
        
        trades_list = list(self.trades.values())
        successful = [t for t in trades_list if t.status == "completed"]
        
        return {
            "total_trades": len(trades_list),
            "successful_trades": len(successful),
            "total_pnl": sum(t.pnl for t in successful),
            "avg_pnl": sum(t.pnl for t in successful) / len(successful) if successful else 0,
            "win_rate": len(successful) / len(trades_list) if trades_list else 0,
            "total_pnl_bps": sum(t.pnl_bps for t in successful),
        }
