"""
交易执行管理器

统一协调交易执行的完整流程：
  信号 → 风控检查 → 创建订单 → 执行(ths_trades/文件信号) → 更新仓位 → 记录
"""
import logging
from datetime import datetime
from typing import Optional

from risk.position import PositionManager
from risk.manager import RiskManager
from execution.order_manager import OrderManager, Order
from execution.file_signal import FileSignalExecutor
from execution.ths_trades_adapter import ThsTradesAdapter
from backtest.cost_model import CostModel

logger = logging.getLogger(__name__)


class ExecutionManager:
    """交易执行管理器，统一协调下单流程。"""

    def __init__(self, risk_manager: RiskManager,
                 position_manager: PositionManager,
                 order_manager: OrderManager,
                 file_signal: FileSignalExecutor,
                 ths_trades: ThsTradesAdapter,
                 cost_model: CostModel = None):
        self.risk = risk_manager
        self.position = position_manager
        self.orders = order_manager
        self.file_signal = file_signal
        self.ths_trades = ths_trades
        self.cost = cost_model or CostModel()

    def execute_signal(self, signal) -> dict:
        """执行交易信号（Signal对象）。"""
        code = signal.code
        action = signal.action
        price = signal.price
        shares = signal.shares
        reason = getattr(signal, 'reason', '')
        strategy = getattr(signal, 'strategy', '')

        return self.execute_signal_direct(code, action, price, shares, reason, strategy)

    def execute_signal_direct(self, code: str, action: str, price: float,
                               shares: int, reason: str = "",
                               strategy: str = "") -> dict:
        """
        直接执行交易（无需Signal对象）。

        Returns:
            {"success": bool, "method": str, "order_id": str, "details": ...}
        """
        action_cn = "买入" if action == "BUY" else "卖出"
        logger.info(f"执行信号: {code} {action_cn} {shares}股 @ {price:.3f} | {reason}")

        # Step 1: 风控检查
        can_trade, risk_msg = self.risk.can_trade(code, action, shares, price)
        if not can_trade:
            logger.warning(f"风控拒绝: {code} {action_cn} - {risk_msg}")
            return {
                "success": False,
                "method": "risk_block",
                "code": code,
                "action": action,
                "error": risk_msg,
            }

        # Step 2: 创建订单
        order = self.orders.create_order(code, action, price, shares, reason, strategy)

        # Step 3: 执行交易
        exec_result = self._do_execute(code, action, price, shares, reason)

        # Step 4: 更新仓位和风控
        if exec_result.get("success"):
            self._post_execute(code, action, shares, price, exec_result)
            self.orders.fill_order(
                order.order_id, price, shares,
                exec_result.get("cost", 0)
            )
            return {
                "success": True,
                "method": exec_result.get("method", "unknown"),
                "order_id": order.order_id,
                "code": code,
                "action": action,
                "shares": shares,
                "price": price,
            }
        else:
            self.orders.reject_order(order.order_id, exec_result.get("error", "Unknown"))
            return {
                "success": False,
                "method": exec_result.get("method", "unknown"),
                "order_id": order.order_id,
                "code": code,
                "action": action,
                "error": exec_result.get("error", "Unknown"),
            }

    def _do_execute(self, code: str, action: str, price: float,
                    shares: int, reason: str) -> dict:
        """实际执行交易。优先级: ths_trades(如启用) → 文件信号"""
        if self.ths_trades.enabled:
            result = self.ths_trades.execute(code, action, price, shares)
            if result.get("success"):
                logger.info(f"ths_trades 执行成功: {code} {action}")
                return result
            else:
                logger.warning(f"ths_trades 失败，降级到文件信号: "
                              f"{result.get('error')}")

        result = self.file_signal.execute(code, action, price, shares, reason)
        return result

    def _post_execute(self, code: str, action: str, shares: int,
                       price: float, exec_result: dict):
        """交易后更新仓位和风控记录。"""
        cost_info = self.cost.calculate(action, price, shares)

        # 更新仓位
        if action == "BUY":
            self.position.open_position(code, price, shares, action)
            pnl = 0
        else:
            settlement = self.position.close_position(code, price, "TRADE")
            pnl = settlement.get("pnl", 0) if settlement else 0
            pnl -= cost_info["total_cost"]

        # 记录到风控
        self.risk.record_trade(code, action, shares, price, pnl)

    def get_status(self) -> dict:
        """获取执行层状态。"""
        return {
            "ths_trades_enabled": self.ths_trades.enabled,
            "ths_trades_online": self.ths_trades.ping() if self.ths_trades.enabled else False,
            "file_signal_dir": self.file_signal.signal_dir,
            "pending_signals": len(self.file_signal.list_pending()),
            "order_stats": self.orders.get_stats(),
        }
