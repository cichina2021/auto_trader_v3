"""
交易成本模型 (Transaction Cost Model)
精确建模A股实际交易成本

A股交易费用：
  买入：佣金(万三,最低5元) + 滑点(千1)
  卖出：佣金(万三,最低5元) + 印花税(千1) + 滑点(千1)
"""
import logging
from typing import Tuple


logger = logging.getLogger(__name__)


class CostModel:
    """A股交易成本模型"""

    # A股标准费率
    COMMISSION_RATE = 0.0003      # 佣金万分之三（常见券商费率）
    COMMISSION_MIN = 5.0          # 佣金最低5元
    STAMP_TAX_RATE = 0.001        # 印花税千分之一（仅卖出）
    SLIPPAGE_RATE = 0.001         # 滑点千分之一

    def __init__(self,
                 commission_rate: float = None,
                 stamp_tax_rate: float = None,
                 slippage_rate: float = None):
        self.commission_rate = commission_rate or self.COMMISSION_RATE
        self.stamp_tax_rate = stamp_tax_rate or self.STAMP_TAX_RATE
        self.slippage_rate = slippage_rate or self.SLIPPAGE_RATE

    def calculate(self, action: str, price: float, shares: int) -> dict:
        """
        计算单笔交易的总成本

        Args:
            action: "BUY" 或 "SELL"
            price: 成交价格
            shares: 成交数量

        Returns:
            {
                "total_cost": 总成本金额,
                "commission": 佣金,
                "stamp_tax": 印花税（仅卖出有）,
                "slippage": 滑点成本,
                "cost_pct": 占交易额的百分比,
                "effective_price": 扣除滑点后的有效价格,
            }
        """
        notional = price * shares

        # ---- 佣金 ----
        commission = max(notional * self.commission_rate, self.COMMISSION_MIN)

        # ---- 印花税（仅卖出）----
        stamp_tax = 0.0
        if action == "SELL":
            stamp_tax = notional * self.stamp_tax_rate

        # ---- 滑点 ----
        slippage = notional * self.slippage_rate

        # ---- 总成本 ----
        total_cost = commission + stamp_tax + slippage
        cost_pct = total_cost / notional if notional > 0 else 0

        # 有效价格（扣减滑点影响）
        if action == "BUY":
            effective_price = price * (1 + self.slippage_rate)
        else:
            effective_price = price * (1 - self.slippage_rate)

        result = {
            "total_cost": round(total_cost, 2),
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "slippage": round(slippage, 2),
            "cost_pct": round(cost_pct, 6),
            "effective_price": round(effective_price, 4),
            "notional": round(notional, 2),
        }

        logger.debug(f"成本[{action}]: {shares}股@{price:.2f} "
                     f"=¥{total_cost:.2f}({cost_pct:.4%})")
        return result

    @staticmethod
    def estimate_round_trip(price: float, shares: int) -> dict:
        """
        估算完整一买一卖的往返成本
        """
        model = CostModel()
        buy_cost = model.calculate("BUY", price, shares)
        sell_cost = model.calculate("SELL", price, shares)

        total_round_trip = buy_cost["total_cost"] + sell_cost["total_cost"]
        notional = price * shares

        return {
            "buy_cost": buy_cost,
            "sell_cost": sell_cost,
            "total_round_trip": round(total_round_trip, 2),
            "round_trip_pct": round(total_round_trip / notional, 6),
            "breakeven_pct": round(
                (sell_cost["cost_pct"] + buy_cost["cost_pct"]) * 100, 4
            ),
        }
