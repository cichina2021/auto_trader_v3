"""
波动率因子 (Volatility Factor)
权重: 25%

核心逻辑：
1. ATR波动率 — 当前波动率相对于历史平均的偏离程度
2. 布林带位置 — 价格在布林带中的位置（超买/超卖）
3. 波动率变化趋势 — 波动率扩张/收缩
4. 日内振幅 — 当日振幅是否异常
"""
import numpy as np
from typing import Optional
from strategy.factors.base import FactorBase, FactorConfig
from strategy.signals import FactorResult
from strategy.indicators import ATR, BOLL, RSI


class VolatilityFactor(FactorBase):
    """波动率因子 — 捕捉市场波动特征"""

    def __init__(self, config: FactorConfig = None):
        if config is None:
            config = FactorConfig(
                name="volatility",
                weight=0.25,
                params={
                    "atr_period": 14,
                    "boll_period": 20,
                    "atr_lookback": 20,
                    "boll_weight": 0.35,
                    "atr_deviation_w": 0.30,
                    "swing_weight": 0.20,
                    "vol_regime_w": 0.15,
                }
            )
        super().__init__(config)

    def calculate(self, klines: list, **kwargs) -> FactorResult:
        if len(klines) < 30:
            return FactorResult(self.name, 0, 0.0, {"error": "数据不足"})

        closes_arr = np.array([k["close"] for k in klines], dtype=float)
        highs_arr = np.array([k["high"] for k in klines], dtype=float)
        lows_arr = np.array([k["low"] for k in klines], dtype=float)

        details = {}
        sub_scores = []

        # ---- 1. 布林带位置 (Bollinger Position) ----
        boll_data = BOLL(klines, self.params["boll_period"])
        boll_score = 0
        if boll_data.get("mid") is not None:
            position_pct = self._calc_boll_position_pct(boll_data)
            details["boll_position_pct"] = round(position_pct, 2)

            if boll_data["position"] == "below_lower":
                # 接近下轨 → 超卖，可能反弹 → 看多信号
                boll_score = min(1.0, (15 - position_pct) / 15 * 0.8 + 0.2)
            elif boll_data["position"] == "above_upper":
                # 接近上轨 → 超买，可能回调 → 看空信号
                boll_score = -min(1.0, (position_pct - 85) / 15 * 0.8 - 0.2)
            elif position_pct < 35:
                boll_score = 0.3   # 偏弱但有支撑
            elif position_pct > 65:
                boll_score = -0.3  # 偏强有压力
            else:
                boll_score = 0.0   # 中性区间

        details["bollinger"] = {**boll_data, "score": round(boll_score, 3)}
        sub_scores.append(boll_score * self.params["boll_weight"])

        # ---- 2. ATR偏离 (ATR Deviation) ----
        atr_val = ATR(klines, self.params["atr_period"])
        atr_score = 0
        if atr_val is not None and len(closes_arr) > self.params["atr_lookback"]:
            current_price = closes_arr[-1]
            atr_ratio = atr_val / current_price * 100  # ATR占价格的百分比

            # 计算历史ATR均值
            historical_atrs = []
            for i in range(self.params["atr_lookback"], len(closes_arr)):
                sub_klines = [
                    {"close": closes_arr[j], "high": highs_arr[j],
                     "low": lows_arr[j], "volume": 0}
                    for j in range(max(0, i - self.params["atr_period"]), i + 1)
                ]
                sub_atr = ATR(sub_klines, self.params["atr_period"])
                if sub_atr and sub_atr > 0:
                    historical_atrs.append(sub_atr / closes_arr[i] * 100)

            if historical_atrs:
                avg_hist_atr = np.mean(historical_atrs)
                deviation = (atr_ratio - avg_hist_atr) / avg_hist_atr if avg_hist_atr > 0 else 0

                if deviation > 0.3:       # 波动率显著扩张
                    atr_score = -0.3       # 高波动→风险增大，偏空
                elif deviation < -0.2:     # 波动率收缩
                    atr_score = 0.2        # 低波动→可能蓄势
                else:
                    atr_score = 0.0

                details["atr_analysis"] = {
                    "current_atr_pct": round(atr_ratio, 4),
                    "avg_hist_atr_pct": round(avg_hist_atr, 4),
                    "deviation": round(deviation, 4),
                }

        sub_scores.append(atr_score * self.params["atr_deviation_w"])

        # ---- 3. 日内/近期振幅 (Swing Analysis) ----
        swing_score = 0
        today_swing = 0.0
        if len(closes_arr) >= 5:
            recent_highs = highs_arr[-5:]
            recent_lows = lows_arr[-5:]
            recent_ranges = [(h - l) / l * 100 for h, l in zip(recent_highs, recent_lows)]
            avg_swing = np.mean(recent_ranges)
            today_swing = float(recent_ranges[-1]) if len(recent_ranges) > 0 else 0.0

            if today_swing > avg_swing * 1.5:
                swing_score = 0.2
            elif today_swing < avg_swing * 0.5:
                swing_score = -0.1

        details["swing_analysis"] = {
            "today_swing_pct": round(today_swing, 2),
            "score": round(swing_score, 3),
        }
        sub_scores.append(swing_score * self.params["swing_weight"])

        # ---- 4. 波动率状态 (Vol Regime) ----
        vol_regime_score = 0
        rsi_val = RSI(klines, 14)
        if rsi_val is not None:
            # 高RSI+高波动=危险区域；低RSI+低波动=潜在机会
            if rsi_val > 70 and abs(boll_score) < 0.3:
                vol_regime_score = -0.3
            elif rsi_val < 30 and abs(boll_score) < 0.3:
                vol_regime_score = 0.3

        sub_scores.append(vol_regime_score * self.params["vol_regime_w"])

        # ---- 综合计算 ----
        total_raw = sum(sub_scores)
        direction = 1 if total_raw > 0.05 else (-1 if total_raw < -0.05 else 0)
        confidence = min(1.0, abs(total_raw))

        details["total_raw"] = round(total_raw, 4)
        details["sub_scores"] = {
            k: round(v, 4) for k, v in zip(
                ["boll", "atr", "swing", "regime"], sub_scores
            )
        }

        return FactorResult(
            name=self.name,
            direction=direction,
            confidence=confidence,
            details=details,
            weight=self.weight,
        )

    @staticmethod
    def _calc_boll_position_pct(boll_data: dict) -> float:
        """计算价格在布林带中的位置百分比 (0~100)"""
        upper = boll_data.get("upper")
        lower = boll_data.get("lower")
        mid = boll_data.get("mid")

        if upper is None or lower is None or upper == lower:
            return 50.0

        # 从原始K线获取当前价（这里用mid近似）
        bandwidth = upper - lower
        pos = (mid - lower) / bandwidth * 100 if bandwidth > 0 else 50.0
        return max(0, min(100, pos))
