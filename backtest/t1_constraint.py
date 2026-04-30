"""
T+1约束执行器
确保回测和实盘交易遵守A股T+1制度：当日买入的股票不能在当日卖出
"""
import logging
from typing import Dict, Set, Optional, Tuple
from datetime import date

logger = logging.getLogger(__name__)


class T1Constraint:
    """T+1交易约束管理器"""

    def __init__(self):
        # 今日买入记录: {code -> 可用日期(即T+1日)}
        self._today_buys: Dict[str, date] = {}
        self._trade_date: Optional[date] = None

    def reset_day(self):
        """新交易日调用 — 清除过期买入记录"""
        today = date.today()
        if self._trade_date and self._trade_date < today:
            # 清除已过T+1的记录
            expired = [c for c, d in self._today_buys.items() if d <= today]
            for c in expired:
                del self._today_buys[c]
            logger.debug(f"T1清理: 移除{len(expired)}条过期记录")

        self._trade_date = today

    def record_buy(self, code: str):
        """记录一笔买入"""
        from datetime import timedelta
        self._today_buys[code] = date.today() + timedelta(days=1)
        logger.debug(f"T1记录: {code} 买入, 可卖于{self._today_buys[code]}")

    def record_sell(self, code: str):
        """记录一笔卖出（不直接影响约束）"""
        pass

    def can_sell(self, code: str, shares: int,
                 available_shares: int) -> Tuple[bool, int]:
        """
        检查是否允许卖出指定数量的股票

        Args:
            code: 股票代码
            shares: 要卖出的数量
            available_shares: 账户中该股票的总可用数量（不含今日买的）

        Returns:
            (是否可卖, 实际可卖数量)
        """
        self.reset_day()

        sellable_date = self._today_buys.get(code)

        if sellable_date is None or sellable_date <= date.today():
            # 该股票没有今日买入，或已过T+1 → 全部可卖
            return True, min(shares, available_shares)

        # 有今日买入 → 只能卖非今日买的部分
        # available_shares 已经是扣除今日买的可用量
        actual_sellable = min(shares, available_shares)

        if actual_sellable > 0:
            return True, actual_sellable
        else:
            logger.warning(f"[{code}] T+1限制: 今日买入无法卖出")
            return False, 0

    @property
    def locked_codes(self) -> Set[str]:
        """返回被T+1锁定的代码集合"""
        self.reset_day()
        return {c for c, d in self._today_buys.items() if d > date.today()}

    @property
    def locked_count(self) -> int:
        """被锁定股票数"""
        return len(self.locked_codes)
