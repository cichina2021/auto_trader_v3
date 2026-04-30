"""
贝叶斯信号融合引擎 (Bayesian Signal Fusion)
将多因子信号通过贝叶斯定理融合为统一的交易信号

核心思想：
  P(盈利 | 因子信号) ∝ P(因子信号 | 盈利) × P(盈利)

  - 先验概率：P(盈利)=0.5（无信息时的基准）
  - 似然度：每个因子信号对"盈利"假设的支持程度
  - 后验概率：融合所有因子后的最终判断
"""
import math
import numpy as np
import logging
from typing import Dict, List, Optional
from strategy.signals import FactorResult, Signal

logger = logging.getLogger(__name__)


class BayesianFusion:
    """
    贝叶斯信号融合器

    将多个因子的独立信号融合为统一的后验概率
    """

    def __init__(self,
                 prior: float = 0.5,
                 min_confidence: float = 0.60):
        """
        Args:
            prior: 先验概率（默认50%认为多空等概率）
            min_confidence: 触发信号的最低后验置信度
        """
        self.prior = prior
        self.min_confidence = min_confidence

    def fuse(self, factor_results: List[FactorResult]) -> dict:
        """
        融合多个因子结果

        Args:
            factor_results: 因子计算结果列表

        Returns:
            {
                "direction": 1 (买) / -1 (卖) / 0 (观望),
                "confidence": 0~1,
                "posterior": 后验概率,
                "factor_contributions": 各因子贡献明细,
                "agreement": 因子一致性统计,
            }
        """
        if not factor_results:
            return {
                "direction": 0, "confidence": 0.0, "posterior": self.prior,
                "factor_contributions": {}, "agreement": {"bullish": 0, "bearish": 0, "neutral": 0},
            }

        # ---- 计算每个因子的似然贡献 ----
        contributions = {}
        log_likelihood_ratio = 0.0

        for fr in factor_results:
            # FactorResult没有enabled字段，所有结果都参与计算
            if fr.confidence == 0:
                continue

            # 似然比: P(signal|profitable) / P(signal|not_profitable)
            # 用因子方向和置信度构建似然模型
            likelihood_bullish = self._likelihood(fr, direction=1)
            likelihood_bearish = self._likelihood(fr, direction=-1)

            if likelihood_bearish > 0 and \
               likelihood_bullish / likelihood_bearish > 1e-10:
                lr = likelihood_bullish / likelihood_bearish
            else:
                lr = 1.0

            if lr > 1e-10:
                log_likelihood_ratio += math.log(lr)

            contributions[fr.name] = {
                "log_lr": round(math.log(lr) if lr > 0 else 0, 4),
                "lr": round(lr, 4),
                "direction": fr.direction,
                "confidence": round(fr.confidence, 4),
                "weight": fr.weight,
            }

        # ---- 计算后验概率 ----
        # 后验 odds = 先验 odds × 乘积(似然比)
        prior_odds = self.prior / (1 - self.prior)
        posterior_odds = prior_odds * math.exp(log_likelihood_ratio)
        posterior = posterior_odds / (1 + posterior_odds)

        # ---- 确定方向和置信度 ----
        if posterior > self.prior + 0.05:
            direction = 1   # 看多
            confidence = abs(posterior - 0.5) * 2  # 映射到0~1
        elif posterior < self.prior - 0.05:
            direction = -1  # 看空
            confidence = abs(posterior - 0.5) * 2
        else:
            direction = 0   # 中性
            confidence = 0.0

        # 因子一致性
        bullish_count = sum(1 for fr in factor_results if fr.direction > 0)
        bearish_count = sum(1 for fr in factor_results if fr.direction < 0)
        neutral_count = len(factor_results) - bullish_count - bearish_count

        result = {
            "direction": direction,
            "confidence": round(min(1.0, confidence), 4),
            "posterior": round(posterior, 6),
            "factor_contributions": contributions,
            "agreement": {
                "bullish": bullish_count,
                "bearish": bearish_count,
                "neutral": neutral_count,
                "total": len(factor_results),
                "consensus_strength": round(
                    max(bullish_count, bearish_count) /
                    max(len(factor_results), 1), 2
                ),
            },
        }

        logger.debug(f"贝叶斯融合: 方向={direction}, "
                     f"置信={result['confidence']:.3f}, "
                     f"后验={posterior:.4f}, "
                     f"一致({bullish_count}/{bearish_count}/{neutral_count})")
        return result

    @staticmethod
    def _likelihood(factor: FactorResult, direction: int) -> float:
        """
        计算给定方向的似然值

        模型：
          - 当因子direction与目标direction一致 → 高似然
          - 不一致 → 低似然
          - 置信度越高，区分度越大
        """
        alignment = factor.direction * direction  # 同号=1, 异号=-1, 零=0

        # 基础似然（中性）
        base_likelihood = 0.5

        # 根据对齐度和置信度调整
        if alignment > 0:
            # 因子支持目标方向
            likelihood = base_likelihood + 0.45 * factor.confidence
        elif alignment < 0:
            # 因子反对目标方向
            likelihood = base_likelihood - 0.40 * factor.confidence
        else:
            # 中性因子不提供信息
            likelihood = base_likelihood

        return max(0.01, min(0.99, likelihood))

    def should_trigger(self, fusion_result: dict,
                       min_agree: int = 2) -> tuple[bool, str]:
        """
        判断是否应触发交易信号

        Args:
            fusion_result: fuse()的返回值
            min_agree: 最少需N个因子方向一致

        Returns:
            (是否触发, 原因描述)
        """
        conf = fusion_result["confidence"]
        direction = fusion_result["direction"]
        agree = fusion_result["agreement"]

        if direction == 0:
            return False, "中性信号，无明确方向"

        if conf < self.min_confidence:
            return False, f"置信度不足 ({conf:.1%} < {self.min_confidence:.0%})"

        max_aligned = max(agree["bullish"], agree["bearish"])
        if max_aligned < min_agree:
            return False, f"因子一致性不足 ({max_aligned} < {min_agree})"

        action = "BUY" if direction > 0 else "SELL"
        return True, f"{action}信号: 置信{conf:.0%}, {max_aligned}个因子一致"
