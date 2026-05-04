"""
量能因子 (Volume Factor)
权重: 20%

核心逻辑：
1. 量比分析 — 当前成交量相对于历史均量的倍数
2. 量价背离 — 价格新高/新低时量能是否配合
3. 成交量趋势 — 近期成交量是否在放大或萎缩
4. 大单追踪（基于量比推断）— 异常放量可能意味着主力进出
"""
import numpy as np
from typing import Optional
from strategy.factors.base import FactorBase, FactorConfig
from strategy.signals import FactorResult
from strategy.indicators import VOLUME_RATIO, MA, OBV


class VolumeFactor(FactorBase):
    """量能因子 — 通过成交量和价格关系判断市场情绪"""

    def __init__(self, config: FactorConfig = None):
        if config is None:
            config = FactorConfig(
                name="volume",
                weight=0.20,
                params={
                    "vr_period": 5,              # 量比周期
                    "vr_threshold_high": 2.5,      # 高量比阈值
                    "vr_threshold_low": 0.6,       # 低量比阈值
                    "vol_ratio_weight": 0.35,
                    "price_volume_divergence_w": 0.30,
                    "obv_trend_w": 0.20,
                    "vol_momentum_w": 0.15,
                }
            )
        super().__init__(config)

    def calculate(self, klines: list, **kwargs) -> FactorResult:
        if len(klines) < 15:
            return FactorResult(self.name, 0, 0.0, {"error": "数据不足"})

        closes_arr = np.array([k["close"] for k in klines], dtype=float)
        volumes_arr = np.array([k["volume"] for k in klines], dtype=float)

        details = {}
        sub_scores = []

        # ---- 1. 量比分析 (Volume Ratio) ----
        vr = VOLUME_RATIO(klines, self.params["vr_period"])
        vr_score = 0
        if vr is not None:
            if vr >= self.params["vr_threshold_high"]:
                # 显著放量 → 关注是否为突破信号
                vr_score = 0.7
            elif vr <= self.params["vr_threshold_low"]:
                # 极度缩量 → 可能变盘
                vr_score = -0.3
            elif 1.5 <= vr < self.params["vr_threshold_high"]:
                # 温和放量 → 正常活跃
                vr_score = 0.3
            elif 0.8 < vr < 1.2:
                # 正常量 → 中性
                vr_score = 0.0

        details["volume_ratio"] = {"value": vr, "score": round(vr_score, 3)}
        sub_scores.append(vr_score * self.params["vol_ratio_weight"])

        # ---- 2. 量价背离 (Price-Volume Divergence) ----
        pv_score = self._calc_price_volume_divergence(closes_arr, volumes_arr, klines)
        details["price_volume_divergence"] = {
            "score": round(pv_score, 3),
        }
        sub_scores.append(pv_score * self.params["price_volume_divergence_w"])

        # ---- 3. OBV趋势 (OBV Trend) ----
        obv_val = OBV(klines)
        obv_score = 0
        if obv_val is not None and len(volumes_arr) > 10:
            # OBV方向与价格方向对比
            price_direction = 1 if closes_arr[-1] > closes_arr[-5] else -1
            obv_direction = 1 if obv_val > 0 else -1

            if price_direction == obv_direction:
                obv_score = 0.3   # 量价齐升/齐降，趋势确认
            else:
                obv_score = -0.2  # 背离预警

        details["obv"] = {"value": obv_val, "score": round(obv_score, 3)}
        sub_scores.append(obv_score * self.params["obv_trend_w"])

        # ---- 4. 成交量动量 (Volume Momentum) ----
        recent_avg_vol = 0.0
        prev_avg_vol = 0.0
        vol_momentum_score = 0
        if len(volumes_arr) > 10:
            recent_avg_vol = float(np.mean(volumes_arr[-5:]))
            prev_avg_vol = float(np.mean(volumes_arr[-10:-5]))
            if prev_avg_vol > 0:
                vol_change = (recent_avg_vol - prev_avg_vol) / prev_avg_vol
                if vol_change > 0.3:
                    vol_momentum_score = 0.25
                elif vol_change < -0.2:
                    vol_momentum_score = -0.15

        details["vol_momentum"] = {
            "recent_5d_avg": round(recent_avg_vol, 0),
            "prev_5d_avg": round(prev_avg_vol, 0),
            "score": round(vol_momentum_score, 3),
        }
        sub_scores.append(vol_momentum_score * self.params["vol_momentum_w"])

        # ---- 综合计算 ----
        total_raw = sum(sub_scores)
        direction = 1 if total_raw > 0.05 else (-1 if total_raw < -0.05 else 0)
        confidence = min(1.0, abs(total_raw))

        details["total_raw"] = round(total_raw, 4)
        details["sub_scores"] = {
            k: round(v, 4) for k, v in zip(
                ["vr", "pv_div", "obv", "vol_mom"], sub_scores
            )
        }

        return FactorResult(
            name=self.name,
            direction=direction,
            confidence=confidence,
            details=details,
            weight=self.weight,
        )

    def _calc_price_volume_divergence(self, closes: np.ndarray,
                                       volumes: np.ndarray,
                                       klines: list) -> float:
        """
        检测量价背离

        Returns:
            分数：正=看多信号，负=看空信号
        """
        if len(closes) < 10:
            return 0.0

        current_price = closes[-1]
        recent_high = float(np.max(closes[-5:]))
        recent_low = float(np.min(closes[-5:]))
        current_vol = volumes[-1]
        avg_vol = float(np.mean(volumes[-6:-1])) if len(volumes) > 5 else current_vol

        score = 0.0

        # 价格创新高但量缩 = 顶背离（看空）
        if current_price >= recent_high * 0.99 and avg_vol > 0:
            vol_ratio = current_vol / avg_vol
            if vol_ratio < 0.8:
                score -= 0.6
            elif vol_ratio < 1.0:
                score -= 0.2

        # 价格创新低但量缩 = 底背离（看多）
        if current_price <= recent_low * 1.01 and avg_vol > 0:
            vol_ratio = current_vol / avg_vol
            if vol_ratio < 0.7:
                score += 0.5  # 缩量企稳
            elif vol_ratio > 1.5:
                score += 0.3  # 放量反弹

        # 放量上涨 = 健康看多
        if current_price > closes[-5] and avg_vol > 0:
            if current_vol / avg_vol > 1.5:
                score += 0.4

        return max(-1.0, min(1.0, score))
