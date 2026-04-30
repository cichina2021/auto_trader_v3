"""
订单管理系统

管理订单的完整生命周期：创建 → 提交 → 成交/取消/拒绝
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """订单数据类。"""
    order_id: str
    code: str
    action: str          # "BUY" / "SELL"
    price: float
    shares: int
    status: str = "pending"  # pending/submitted/filled/cancelled/rejected
    filled_price: Optional[float] = None
    filled_shares: int = 0
    commission: float = 0.0
    create_time: datetime = field(default_factory=datetime.now)
    update_time: Optional[datetime] = None
    error_msg: str = ""
    reason: str = ""        # 触发该订单的信号原因
    strategy: str = ""      # 来源策略名称

    @property
    def is_completed(self) -> bool:
        return self.status in ("filled", "cancelled", "rejected")

    @property
    def turnover(self) -> float:
        """成交金额。"""
        if self.filled_price and self.filled_shares > 0:
            return self.filled_price * self.filled_shares
        return 0.0

    @property
    def pnl(self) -> float:
        """已实现盈亏（仅对已成交的卖出订单有效）。"""
        return 0.0  # PnL由PositionManager计算

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "code": self.code,
            "action": self.action,
            "price": self.price,
            "shares": self.shares,
            "status": self.status,
            "filled_price": self.filled_price,
            "filled_shares": self.filled_shares,
            "commission": self.commission,
            "create_time": self.create_time.strftime("%H:%M:%S"),
            "update_time": (self.update_time.strftime("%H:%M:%S")
                           if self.update_time else ""),
            "error_msg": self.error_msg,
            "reason": self.reason,
            "strategy": self.strategy,
        }


class OrderManager:
    """订单管理器，跟踪所有订单生命周期。"""

    def __init__(self):
        self.orders: List[Order] = []
        self._counter = 0

    def create_order(self, code: str, action: str, price: float,
                     shares: int, reason: str = "",
                     strategy: str = "") -> Order:
        """
        创建新订单。

        Args:
            code: 股票代码
            action: BUY / SELL
            price: 目标价格
            shares: 股数
            reason: 触发原因
            strategy: 来源策略

        Returns:
            Order对象
        """
        self._counter += 1
        order = Order(
            order_id=f"ORD{self._counter:06d}",
            code=code,
            action=action,
            price=price,
            shares=shares,
            reason=reason,
            strategy=strategy,
        )
        self.orders.append(order)
        logger.info(f"订单创建: {order.order_id} {code} {action} "
                   f"{shares}股 @ {price:.3f} | {reason}")
        return order

    def update_order(self, order_id: str, status: str, **kwargs):
        """
        更新订单状态。

        Args:
            order_id: 订单ID
            status: 新状态
            **kwargs: 其他字段更新
        """
        for order in self.orders:
            if order.order_id == order_id:
                order.status = status
                order.update_time = datetime.now()
                for k, v in kwargs.items():
                    if hasattr(order, k):
                        setattr(order, k, v)
                logger.info(f"订单更新: {order_id} → {status}")
                return

        logger.warning(f"订单不存在: {order_id}")

    def fill_order(self, order_id: str, filled_price: float,
                   filled_shares: int, commission: float = 0):
        """标记订单为已成交。"""
        self.update_order(
            order_id, "filled",
            filled_price=filled_price,
            filled_shares=filled_shares,
            commission=commission,
        )

    def reject_order(self, order_id: str, error_msg: str):
        """标记订单为被拒绝。"""
        self.update_order(order_id, "rejected", error_msg=error_msg)

    def cancel_order(self, order_id: str):
        """取消订单。"""
        self.update_order(order_id, "cancelled")

    def get_today_orders(self) -> List[Order]:
        """获取今日所有订单。"""
        today = datetime.now().date()
        return [o for o in self.orders if o.create_time.date() == today]

    def get_pending_orders(self) -> List[Order]:
        """获取待处理订单。"""
        return [o for o in self.orders if o.status == "pending"]

    def get_filled_orders(self) -> List[Order]:
        """获取已成交订单。"""
        return [o for o in self.orders if o.status == "filled"]

    def get_orders_by_code(self, code: str) -> List[Order]:
        """获取指定股票的所有订单。"""
        return [o for o in self.orders if o.code == code]

    def get_recent_orders(self, limit: int = 20) -> List[dict]:
        """获取最近N条订单（按时间倒序）。"""
        recent = sorted(self.orders, key=lambda o: o.create_time, reverse=True)
        return [o.to_dict() for o in recent[:limit]]

    def get_stats(self) -> dict:
        """获取订单统计。"""
        today_orders = self.get_today_orders()
        return {
            "total_orders": len(self.orders),
            "today_orders": len(today_orders),
            "pending": len(self.get_pending_orders()),
            "filled": len(self.get_filled_orders()),
            "rejected": len([o for o in self.orders if o.status == "rejected"]),
            "cancelled": len([o for o in self.orders if o.status == "cancelled"]),
        }
