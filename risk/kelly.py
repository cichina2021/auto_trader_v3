"""
Kelly公式仓位计算器 (Kelly Criterion Position Sizer)

Kelly Criterion:
  f* = (b × p - q) / b

其中：
  b = 平均盈利 / |平均亏损|（盈亏比）
  p = 胜率（历史交易中盈利交易占比）
  q = 1 - p

实际使用分数Kelly（0.25x），大幅降低破产风险
"""
import logging
from typing import Optional, List, Dict
from datetime import datetime, date

logger = logging.getLogger(__name__)


class KellyCalculator:
    """Kelly公式仓位管理"""

    def __init__(self,
                 fraction: float = 0.25,
                 cap: float = 0.30,
                 default_fraction: float = 0.05):
        """
        Args:
            fraction: 分数Kelly系数（0.25 = 保守，0.5 = 激进）
            cap: 单笔最大仓位占比（不超过资金的X%）
            default_fraction: 无足够历史数据时的默认仓位比例
        """
        self.fraction = fraction
        self.cap = cap
        self.default_fraction = default_fraction

    def calculate(self, trade_history: List[dict] = None) -> dict:
        """
        计算最优仓位比例

        Args:
            trade_history: 历史交易记录列表，每项包含 pnl 字段

        Returns:
            {
                "kelly_fraction": 最优f*值,
                "adjusted_fraction": 分数Kelly后的实际建议仓位,
                "cap_adjusted": 经过上限调整后的最终仓位,
                "win_rate": 历史胜率,
                "win_loss_ratio": 盈亏比,
                "trades_count": 使用的交易数,
                "confidence": 计算置信度("high"/"medium"/"low"),
            }
        """
        if not trade_history or len(trade_history) < 10:
            # 数据不足，使用默认值
            return {
                "kelly_fraction": 0.0,
                "adjusted_fraction": self.default_fraction,
                "cap_adjusted": min(self.default_fraction, self.cap),
                "win_rate": 0.5,
                "win_loss_ratio": 1.0,
                "trades_count": len(trade_history) if trade_history else 0,
                "confidence": "low",
            }

        # ---- 提取盈亏数据 ----
        pnls = [t.get("pnl", 0) for t in trade_history if t.get("pnl") is not None]
        if not pnls:
            return self._default_result(0)

        n_trades = len(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        # ---- 计算统计量 ----
        win_rate = len(wins) / n_trades if n_trades > 0 else 0.5
        p = win_rate
        q = 1 - p

        avg_win = sum(wins) / len(wins) if wins else 1.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 1.0

        b = avg_win / avg_loss if avg_loss > 0 else 1.0  # 盈亏比

        # ---- Kelly公式 ----
        if b == 0 or q >= 1:
            kelly_f = 0.0
        else:
            kelly_f = (b * p - q) / b

        # 边界处理：负值→不交易；过大→限制
        kelly_f = max(0, min(kelly_f, 0.50))  # 理论上不超过50%

        # 分数Kelly
        adjusted = kelly_f * self.fraction
        cap_adjusted = min(adjusted, self.cap)

        # ---- 置信度评估 ----
        if n_trades >= 50:
            confidence = "high"
        elif n_trades >= 20:
            confidence = "medium"
        else:
            confidence = "low"

        result = {
            "kelly_fraction": round(kelly_f, 4),
            "adjusted_fraction": round(adjusted, 4),
            "cap_adjusted": round(cap_adjusted, 4),
            "win_rate": round(win_rate, 4),
            "win_loss_ratio": round(b, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "trades_count": n_trades,
            "confidence": confidence,
        }

        logger.debug(f"Kelly计算: f*={kelly_f:.3f}, "
                     f"分数={adjusted:.3f}, "
                     f"胜率={win_rate:.1%}(n={n_trades})")
        return result

    def calc_shares(self,
                    capital: float,
                    price: float,
                    kelly_result: dict,
                    max_shares: int = None) -> int:
        """
        根据Kelly结果计算建议股数

        Args:
            capital: 可用资金
            price: 当前价格
            kelly_result: calculate()的返回值
            max_shares: 最大允许股数（如底仓限制）

        Returns:
            建议股数（取整到100的倍数，即手数）
        """
        if price <= 0 or capital <= 0:
            return 0

        position_value = capital * kelly_result["cap_adjusted"]
        raw_shares = int(position_value / price / 100) * 100  # 取整到100

        if max_shares and max_shares > 0:
            raw_shares = min(raw_shares, max_shares)

        return max(100, raw_shares)  # 至少1手

    def _default_result(self, count: int) -> dict:
        return {
            "kelly_fraction": 0.0,
            "adjusted_fraction": self.default_fraction,
            "cap_adjusted": min(self.default_fraction, self.cap),
            "win_rate": 0.5,
            "win_loss_ratio": 1.0,
            "trades_count": count,
            "confidence": "low",
        }
