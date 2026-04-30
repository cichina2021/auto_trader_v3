"""
交易限额检查器 (Trading Limits Checker)
多层风控规则执行
"""
import logging
from typing import List, Optional, Tuple
from datetime import datetime, date
from collections import defaultdict

from config.risk_params import (
    DAILY_LOSS_HARD_STOP, DAILY_LOSS_WARNING, DAILY_LOSS_ABS_CAP,
    MAX_POSITION_SINGLE, MAX_POSITION_TOTAL,
    MAX_TRADES_PER_STOCK, MAX_TRADES_DAILY,
    CONSECUTIVE_LOSS_LIMIT, CIRCUIT_BREAKER_MINUTES,
)

logger = logging.getLogger(__name__)


class LimitsChecker:
    """交易限额与熔断管理器"""

    def __init__(self):
        self._trades_today: List[dict] = []
        self._daily_pnl: float = 0.0
        self._trade_date: date = datetime.now().date()
        self._stock_trade_count: dict = defaultdict(int)  # code -> count
        self._consecutive_losses: int = 0
        self._circuit_breaker_until: Optional[datetime] = None
        self._halted: bool = False
        self._halt_reason: str = ""

    # ================================================================
    # 核心接口：检查是否允许交易
    # ================================================================

    def can_trade(self,
                  code: str,
                  action: str,
                  shares: int,
                  price: float,
                  equity: float) -> Tuple[bool, str]:
        """
        全面风控检查（按优先级排序）

        Returns:
            (是否允许, 拒绝原因)
        """
        if not action or not code:
            return False, "无效的交易参数"

        # ---- Layer 0: 熔断检查 ----
        ok, reason = self._check_circuit_breaker()
        if not ok:
            return False, reason

        # ---- Layer 1: 日亏损限额 ----
        ok, reason = self._check_daily_loss(equity)
        if not ok:
            return False, reason

        # ---- Layer 2: 单股仓位限制 ----
        ok, reason = self._check_single_position(code, price, shares, equity)
        if not ok:
            return False, reason

        # ---- Layer 3: 总仓位限制 ----
        ok, reason = self._check_total_position(price * shares, equity)
        if not ok:
            return False, reason

        # ---- Layer 4: 交易频率限制 ----
        ok, reason = self._check_trade_frequency(code)
        if not ok:
            return False, reason

        # ---- 全部通过 ----
        return True, "✓ 风控检查通过"

    # ================================================================
    # 各层检查实现
    # ================================================================

    def _check_circuit_breaker(self) -> Tuple[bool, str]:
        """Layer 0: 熔断器"""
        if self._circuit_breaker_until is not None:
            if datetime.now() < self._circuit_breaker_until:
                remaining = (self._circuit_breaker_until - datetime.now()).seconds
                return False, f"🔴 熔断中，剩余{remaining}秒"
            else:
                # 熔断到期，恢复
                logger.info("熔断解除，恢复正常交易")
                self._circuit_breaker_until = None
                self._halted = False
                self._halt_reason = ""

        if self._halted:
            return False, f"⛔ 已暂停: {self._halt_reason}"

        return True, ""

    def _check_daily_loss(self, equity: float) -> Tuple[bool, str]:
        """Layer 1: 日亏损限额"""
        if equity <= 0:
            return False, "权益为0或负数"

        loss_pct = abs(min(0, self._daily_pnl)) / equity
        loss_abs = abs(min(0, self._daily_pnl))

        # 硬停线
        if loss_pct >= DAILY_LOSS_HARD_STOP or loss_abs >= DAILY_LOSS_ABS_CAP:
            self._trigger_circuit_breaker(f"日亏达{loss_pct:.1%}({loss_abs:.0f}元)")
            return False, f"🔴 日亏损超限! {loss_pct:.1%} (>{DAILY_LOSS_HARD_STOP:.0%})"

        # 警告线
        if loss_pct >= DAILY_LOSS_WARNING:
            return False, f"⚡ 日亏损接近警告线! {loss_pct:.1%} (>{DAILY_LOSS_WARNING:.0%})"

        return True, ""

    def _check_single_position(self, code: str, price: float,
                                shares: int, equity: float) -> Tuple[bool, str]:
        """Layer 2: 单股仓位不超过30%"""
        position_value = price * shares
        position_pct = position_value / equity if equity > 0 else 0

        if position_pct > MAX_POSITION_SINGLE:
            return False, (
                f"单股仓位超限! {position_pct:.1%} "
                f"(>{MAX_POSITION_SINGLE:.0%}, "
                f"金额{position_value:.0f}/{equity:.0f})"
            )

        return True, ""

    def _check_total_position(self, new_order_value: float,
                               equity: float) -> Tuple[bool, str]:
        """Layer 3: 总仓位不超过70%"""
        # 当前已占用资金（简化：用今日已交易金额近似）
        used_capital = sum(
            t.get("price", 0) * t.get("shares", 0)
            for t in self._trades_today
        )
        total_after = used_capital + new_order_value
        total_pct = total_after / equity if equity > 0 else 0

        if total_pct > MAX_POSITION_TOTAL:
            return False, (
                f"总仓位超限! {total_pct:.1%} "
                f"(>{MAX_POSITION_TOTAL:.0%})"
            )

        return True, ""

    def _check_trade_frequency(self, code: str) -> Tuple[bool, str]:
        """Layer 4: 交易频率限制"""
        stock_count = self._stock_trade_count.get(code, 0)

        if stock_count >= MAX_TRADES_PER_STOCK:
            return False, (
                f"{code}今日已达最大交易次数 "
                f"({stock_count}>={MAX_TRADES_PER_STOCK})"
            )

        total_count = len(self._trades_today)
        if total_count >= MAX_TRADES_DAILY:
            return False, (
                f"全局已达日交易上限 "
                f"({total_count}>={MAX_TRADES_DAILY})"
            )

        return True, ""

    # ================================================================
    # 记录与状态更新
    # ================================================================

    def record_trade(self, trade: dict):
        """
        记录一笔交易并更新状态

        trade应包含: code, action, price, shares, pnl(可选)
        """
        self._trades_today.append(trade)

        code = trade.get("code", "")
        self._stock_trade_count[code] += 1

        # 更新日PnL
        pnl = trade.get("pnl")
        if pnl is not None:
            self._daily_pnl += pnl

            # 连续亏损计数
            if pnl < 0:
                self._consecutive_losses += 1
                if self._consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
                    self._trigger_circuit_breaker(
                        f"连续亏损{self._consecutive_losses}次"
                    )
            else:
                self._consecutive_losses = max(0, self._consecutive_losses - 1)

        logger.debug(
            f"记录交易: [{code}] {trade.get('action','')} "
            f"x{trade.get('shares',0)} @{trade.get('price',0):.2f} "
            f"PnL={pnl:+.2f}" if pnl is not None else ""
            f"| 日PnL={self._daily_pnl:+.2f}"
        )

    def _trigger_circuit_breaker(self, reason: str):
        """触发熔断"""
        from datetime import timedelta
        self._halted = True
        self._halt_reason = reason
        self._circuit_breaker_until = datetime.now() + timedelta(
            seconds=CIRCUIT_BREAKER_MINUTES * 60
        )
        logger.warning(f"🔴 触发熔断: {reason}, "
                       f"暂停{CIRCUIT_BREAKER_MINUTES}分钟")

    # ================================================================
    # 状态查询
    # ================================================================

    def get_summary(self) -> dict:
        """返回风控摘要"""
        return {
            "date": str(self._trade_date),
            "trades_today": len(self._trades_today),
            "daily_pnl": round(self._daily_pnl, 2),
            "stock_counts": dict(self._stock_trade_count),
            "consecutive_losses": self._consecutive_losses,
            "halted": self._halted,
            "halt_reason": self._halt_reason,
            "circuit_breaker_until":
                str(self._circuit_breaker_until) if self._circuit_breaker_until else None,
        }

    def reset_day(self):
        """新交易日重置"""
        self._trades_today.clear()
        self._daily_pnl = 0.0
        self._trade_date = datetime.now().date()
        self._stock_trade_count.clear()
        self._consecutive_losses = 0
        if not self._halted:
            self._circuit_breaker_until = None
