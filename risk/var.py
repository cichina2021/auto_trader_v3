"""
VaR风险价值计算器 (Value at Risk Calculator)

使用历史模拟法（Historical Simulation）计算VaR
在95%置信度下，评估单日最大预期亏损
"""
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class VaRCalculator:
    """VaR风险价值计算"""

    def __init__(self,
                 confidence: float = 0.95,
                 limit_pct: float = 0.03,
                 warning_pct: float = 0.015,
                 min_samples: int = 100):
        """
        Args:
            confidence: 置信度 (默认95%)
            limit_pct: VaR上限占资金比例 (3%)
            warning_pct: 警告阈值占资金比例 (1.5%)
            min_samples: 计算所需最少样本数
        """
        self.confidence = confidence
        self.limit_pct = limit_pct
        self.warning_pct = warning_pct
        self.min_samples = min_samples

    def calculate(self, returns: List[float] = None) -> dict:
        """
        计算历史模拟VaR

        Args:
            returns: 日收益率序列

        Returns:
            {
                "var_pct": VaR百分比,
                "var_absolute": VaR金额（基于equity）,
                "exceeds_limit": 是否超限,
                "exceeds_warning": 是否触发警告,
                "confidence_level": 实际置信度,
                "sample_count": 样本数,
                "expected_shortfall": ES(条件VaR),
            }
        """
        if not returns or len(returns) < min(self.min_samples, 30):
            return {
                "var_pct": self.warning_pct * 2,
                "var_absolute": 0,
                "exceeds_limit": False,
                "exceeds_warning": False,
                "confidence_level": self.confidence,
                "sample_count": len(returns) if returns else 0,
                "expected_shortfall": 0,
                "status": "insufficient_data",
            }

        arr = np.array(returns, dtype=float)
        n = len(arr)

        # ---- 历史模拟法VaR ----
        # 排序后取分位数
        sorted_returns = np.sort(arr)
        index = int((1 - self.confidence) * n)
        if index >= n:
            index = n - 1

        var_value = abs(sorted_returns[index])  # 取绝对值（亏损为负）

        # ---- 条件期望损失 Expected Shortfall (CVaR/ES) ----
        tail_returns = sorted_returns[:max(index + 1, 1)]
        es = abs(np.mean(tail_returns)) if len(tail_returns) > 0 else var_value

        result = {
            "var_pct": round(float(var_value), 6),
            "var_absolute": 0,  # 需要外部传入equity才能计算
            "exceeds_limit": var_value > self.limit_pct,
            "exceeds_warning": var_value > self.warning_pct,
            "confidence_level": self.confidence,
            "sample_count": n,
            "expected_shortfall": round(float(es), 6),
            "worst_return": round(float(sorted_returns[0]), 6),
            "status": "ok",
        }

        logger.debug(f"VaR计算: {result['var_pct']:.4%} "
                     f"(n={n}, {'超限!' if result['exceeds_limit'] else '正常'})")
        return result

    def check_limit(self, var_result: dict,
                     equity: float = None) -> tuple[bool, str]:
        """
        检查VaR是否在可接受范围内

        Returns:
            (是否安全, 描述文字)
        """
        if var_result.get("status") == "insufficient_data":
            return True, "数据不足，跳过VaR检查"

        var_pct = var_result.get("var_pct", 0)

        if var_pct > self.limit_pct:
            return False, f"⚠️ VaR超限! ({var_pct:.2%} > {self.limit_pct:.0%})"

        if var_pct > self.warning_pct:
            return True, f"⚡ VaR接近警告线 ({var_pct:.2%} < {self.limit_pct:.0%})"

        return True, f"✓ VaR正常 ({var_pct:.2%})"

    def update_with_equity(self, var_result: dict,
                           equity: float) -> dict:
        """根据权益计算VaR绝对金额"""
        var_result["var_absolute"] = round(
            equity * var_result["var_pct"], 2
        )
        var_result["es_absolute"] = round(
            equity * var_result.get("expected_shortfall", 0), 2
        )
        return var_result
