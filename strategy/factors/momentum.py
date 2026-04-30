"""
动量因子 (Momentum Factor)
权重: 30%

核心逻辑：
1. 价格动量：N日收益率、加速度
2. 趋势强度：均线排列状态（多头/空头排列）
3. 短期突破：同日涨幅是否超阈值
"""
import numpy as np
from typing import Optional
from strategy.factors.base import FactorBase, FactorConfig
from strategy.signals import FactorResult
from strategy.indicators import MA, EMA, MACD, RSI


class MomentumFactor(FactorBase):
    """动量因子 — 捕捉价格趋势和动能"""

    def __init__(self, config: FactorConfig = None):
        if config is None:
            config = FactorConfig(
                name="momentum",
                weight=0.30,
                params={
                    "short_period": 5,
                    "mid_period": 10,
                    "long_period": 20,
                    "surge_threshold": 3.0,   # 同日涨幅阈值(%)
                    "ma_alignment_weight": 0.35, # 均线排列权重
                    "return_momentum_w": 0.35,  # 收益动量权重
                    "macd_trend_w": 0.20,       # MACD趋势权重
                    "rsi_momentum_w": 0.10,      # RSI动量权重
                }
            )
        super().__init__(config)

    def calculate(self, klines: list, **kwargs) -> FactorResult:
        if len(klines) < 25:
            return FactorResult(self.name, 0, 0.0, {"error": "数据不足"})

        closes_arr = np.array([k["close"] for k in klines], dtype=float)

        details = {}
        sub_scores = []

        # ---- 1. 均线排列 (MA Alignment) ----
        ma5 = MA(klines, self.params["short_period"])
        ma10 = MA(klines, self.params["mid_period"])
        ma20 = MA(klines, self.params["long_period"])

        ma_score = 0
        ma_direction = 0
        if ma5 and ma10 and ma20:
            if ma5 > ma10 > ma20:
                ma_score = 1.0    # 完美多头排列
                ma_direction = 1
            elif ma5 > ma10 and ma10 < ma20:
                ma_score = 0.4    # 短期强但中期弱
                ma_direction = 0.3
            elif ma5 < ma10 < ma20:
                ma_score = -1.0   # 完美空头排列
                ma_direction = -1
            elif ma5 < ma10 and ma10 > ma20:
                ma_score = -0.4
                ma_direction = -0.3
            else:
                ma_score = 0.0

        details["ma_alignment"] = {
            "score": ma_score, "ma5": ma5, "ma10": ma10, "ma20": ma20
        }
        sub_scores.append(ma_score * self.params["ma_alignment_weight"])

        # ---- 2. 收益动量 (Return Momentum) ----
        current_price = closes_arr[-1]
        ret_5d = (current_price - closes_arr[-6]) / closes_arr[-6] * 100 \
            if len(closes_arr) > 5 else 0
        ret_10d = (current_price - closes_arr[-11]) / closes_arr[-11] * 100 \
            if len(closes_arr) > 10 else 0

        momentum_score = 0
        # 正加速度：短期收益 > 中期收益 > 0 → 看多
        if ret_5d > 0 and ret_10d > 0 and ret_5d > ret_10d:
            momentum_score = min(1.0, abs(ret_5d) / 3.0)  # 按3%封顶归一化
        elif ret_5d > 0 and ret_10d <= 0:
            momentum_score = 0.3  # 反转信号，但短期有动能
        elif ret_5d < 0 and ret_10d < ret_5d:
            momentum_score = -min(1.0, abs(ret_5d) / 3.0)  # 加速下跌
        elif ret_5d < -self.params["surge_threshold"]:
            momentum_score = -0.8  # 大幅下跌
        elif ret_5d > self.params["surge_threshold"]:
            momentum_score = 0.8   # 大幅上涨

        details["return_momentum"] = {
            "ret_5d_pct": round(ret_5d, 2),
            "ret_10d_pct": round(ret_10d, 2),
            "score": round(momentum_score, 3),
        }
        sub_scores.append(momentum_score * self.params["return_momentum_w"])

        # ---- 3. MACD趋势确认 ----
        macd_data = MACD(klines)
        macd_score = 0
        if macd_data.get("macd") is not None:
            hist = macd_data.get("histogram", 0)
            cross = macd_data.get("cross")
            if hist > 0:
                macd_score = min(0.8, hist / 0.05)
            elif hist < 0:
                macd_score = max(-0.8, hist / 0.05)
            if cross == "golden":
                macd_score += 0.2
            elif cross == "dead":
                macd_score -= 0.2
            macd_score = max(-1.0, min(1.0, macd_score))

        details["macd_trend"] = macd_data
        sub_scores.append(macd_score * self.params["macd_trend_w"])

        # ---- 4. RSI动量 ----
        rsi_val = RSI(klines, 14)
        rsi_score = 0
        if rsi_val is not None:
            if rsi_val > 70:
                rsi_score = -0.3  # 超买区域
            elif rsi_val < 30:
                rsi_score = 0.3   # 超卖区域
            elif 45 < rsi_val < 65:
                rsi_score = 0.2   # 健康区间偏多
            else:
                rsi_score = 0.0

        details["rsi"] = rsi_val
        sub_scores.append(rsi_score * self.params["rsi_momentum_w"])

        # ---- 综合计算 ----
        total_raw = sum(sub_scores)
        direction = 1 if total_raw > 0.05 else (-1 if total_raw < -0.05 else 0)
        confidence = min(1.0, abs(total_raw))

        details["total_raw"] = round(total_raw, 4)
        details["sub_scores"] = {k: round(v, 4) for k, v in zip(
            ["ma", "momentum", "macd", "rsi"], sub_scores
        )}

        return FactorResult(
            name=self.name,
            direction=direction,
            confidence=confidence,
            details=details,
            weight=self.weight,
        )
