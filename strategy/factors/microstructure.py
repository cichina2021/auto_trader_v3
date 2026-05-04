"""
微观结构因子 (Microstructure Factor)
权重: 25%

核心逻辑：
1. 订单流不平衡 (OFI) — 主动买入vs卖出压力
2. 盘口压力分析 — 基于量比和价格变化推断买卖力量对比
3. 日内价格路径 — 分时走势形态（V型/W型/M头等）
4. 换手率异常 — 是否有主力进出迹象

注意：由于公开免费数据源不提供Level-2逐笔成交数据，
本因子通过可获取的K线/行情数据推断微观结构特征。
"""
import numpy as np
from typing import Optional, Dict
from strategy.factors.base import FactorBase, FactorConfig
from strategy.signals import FactorResult
from strategy.indicators import MA, VWAP, VOLUME_RATIO


class MicrostructureFactor(FactorBase):
    """
    微观结构因子 — 通过可观测数据推断订单流和市场微观特征
    """

    def __init__(self, config: FactorConfig = None):
        if config is None:
            config = FactorConfig(
                name="microstructure",
                weight=0.25,
                params={
                    "ofi_weight": 0.35,
                    "pressure_w": 0.30,
                    "path_pattern_w": 0.20,
                    "turnover_w": 0.15,
                }
            )
        super().__init__(config)

    def calculate(self, klines: list, **kwargs) -> FactorResult:
        if len(klines) < 20:
            return FactorResult(self.name, 0, 0.0, {"error": "数据不足"})

        # 获取实时行情（如果有传入）
        realtime = kwargs.get("realtime", {})
        current_price = realtime.get("price") or (klines[-1]["close"] if klines else None)

        closes_arr = np.array([k["close"] for k in klines], dtype=float)
        highs_arr = np.array([k["high"] for k in klines], dtype=float)
        lows_arr = np.array([k["low"] for k in klines], dtype=float)
        volumes_arr = np.array([k["volume"] for k in klines], dtype=float)

        details: Dict[str, any] = {}
        sub_scores = []

        # ---- 1. 订单流不平衡 (Order Flow Imbalance) ----
        ofi_result = self._estimate_ofi(closes_arr, highs_arr, lows_arr, volumes_arr)
        details["order_flow_imbalance"] = ofi_result
        sub_scores.append(ofi_result.get("score", 0) * self.params["ofi_weight"])

        # ---- 2. 盘口压力 (Pressure Analysis) ----
        pressure_score = self._analyze_pressure(
            klines, closes_arr, volumes_arr, realtime
        )
        details["pressure"] = {"score": round(pressure_score, 3)}
        sub_scores.append(pressure_score * self.params["pressure_w"])

        # ---- 3. 日内价格路径 (Intraday Path Pattern) ----
        path_score = self._detect_path_pattern(closes_arr, highs_arr, lows_arr)
        details["path_pattern"] = {"score": round(path_score, 3)}
        sub_scores.append(path_score * self.params["path_pattern_w"])

        # ---- 4. 成交活跃度 (Turnover Activity) ----
        turnover_score = self._analyze_turnover(closes_arr, volumes_arr)
        details["turnover"] = {"score": round(turnover_score, 3)}
        sub_scores.append(turnover_score * self.params["turnover_w"])

        # ---- 综合计算 ----
        total_raw = sum(sub_scores)
        direction = 1 if total_raw > 0.05 else (-1 if total_raw < -0.05 else 0)
        confidence = min(1.0, abs(total_raw))

        details["total_raw"] = round(total_raw, 4)
        details["sub_scores"] = {
            k: round(v, 4) for k, v in zip(
                ["ofi", "pressure", "path", "turnover"], sub_scores
            )
        }

        return FactorResult(
            name=self.name,
            direction=direction,
            confidence=confidence,
            details=details,
            weight=self.weight,
        )

    def _estimate_ofi(self, closes: np.ndarray, highs: np.ndarray,
                       lows: np.ndarray, volumes: np.ndarray) -> dict:
        """
        估算订单流不平衡 (Order Flow Imbalance)

        使用K线数据近似OFI：
        - 阳线(收盘>开盘) → 买方主导，成交量记为buy_volume
        - 阴线(收盘<开盘) → 卖方主导，成交量记为sell_volume

        OFI = (buy_vol - sell_vol) / total_vol ∈ [-1, 1]
        """
        if len(closes) < 5:
            return {"ofi_value": 0, "score": 0, "details": {}}

        # 从 klines 取 open（OFI需要判断阴线/阳线）
        # 用收盘价相对前一根的变化方向近似判断多空（降级方案）
        n = min(len(closes), 10)
        buy_vol_total = 0.0
        sell_vol_total = 0.0

        for i in range(max(1, len(closes) - n), len(closes)):
            vol = float(volumes[i]) if i < len(volumes) else 0
            # 用收盘价相对中价的位置判断多空方向
            mid_price = (float(highs[i]) + float(lows[i])) / 2 \
                if i < len(highs) and i < len(lows) else closes[i]

            if closes[i] >= mid_price:
                buy_vol_total += vol
            else:
                sell_vol_total += vol

        total_vol = buy_vol_total + sell_vol_total
        if total_vol == 0:
            return {"ofi_value": 0, "score": 0, "details": {}}

        ofi = (buy_vol_total - sell_vol_total) / total_vol

        # OFI转换为分数
        score = ofi * 0.8  # 缩放到合理范围

        return {
            "ofi_value": round(ofi, 4),
            "score": round(score, 4),
            "details": {
                "buy_ratio": round(buy_vol_total / total_vol, 4),
                "sell_ratio": round(sell_vol_total / total_vol, 4),
            }
        }

    def _analyze_pressure(self, klines: list, closes: np.ndarray,
                           volumes: np.ndarray, realtime: dict) -> float:
        """
        分析盘口买卖压力

        结合：涨跌幅、量比、VWAP偏离度综合判断
        """
        score = 0.0
        change_pct = realtime.get("change_pct", 0)
        vr = VOLUME_RATIO(klines, 5)

        vwap = VWAP(klines)
        current_price = realtime.get("price") or (closes[-1] if len(closes) > 0 else 0)

        # VWAP偏离度：价在VWAP上方→偏强；下方→偏弱
        if vwap and vwap > 0 and current_price > 0:
            vwap_deviation = (current_price - vwap) / vwap * 100
            if vwap_deviation > 0.8:
                score += 0.3   # 显著高于均价→买方强
            elif vwap_deviation < -0.8:
                score -= 0.3   # 显著低于均价→卖方强

        # 量+价配合
        if vr and vr > 1.5 and change_pct > 0:
            score += 0.3       # 放量上涨
        elif vr and vr > 1.5 and change_pct < 0:
            score -= 0.4       #放量下跌（更危险）
        elif vr and vr < 0.6 and change_pct > 0:
            score += 0.1       # 缩量上涨（温和）
        elif vr and vr < 0.6 and change_pct < 0:
            score -= 0.05      # 缩量下跌

        return max(-1.0, min(1.0, score))

    def _detect_path_pattern(self, closes: np.ndarray,
                              highs: np.ndarray, lows: np.ndarray) -> float:
        """
        检测近期价格走势形态

        识别：V型反转、W底、M头、单边趋势等
        """
        if len(closes) < 10:
            return 0.0

        score = 0.0
        recent_n = min(15, len(closes))
        recent_closes = closes[-recent_n:]

        # 计算拐点数量
        turns = 0
        for i in range(2, len(recent_closes)):
            diff_prev = recent_closes[i-1] - recent_closes[i-2]
            diff_curr = recent_closes[i] - recent_closes[i-1]
            if diff_prev * diff_curr < 0:  # 方向改变
                turns += 1

        # V型/U型：先跌后升（看多）
        if recent_closes[0] > recent_closes[len(recent_closes)//2] and \
           recent_closes[-1] > recent_closes[len(recent_closes)//2]:
            score += 0.25
            details_path = "V_shape_bullish"

        # 倒V型/A形：先升后跌（看空）
        elif recent_closes[0] < recent_closes[len(recent_closes)//2] and \
             recent_closes[-1] < recent_closes[len(recent_closes)//2]:
            score -= 0.25
            details_path = "inverted_V_bearish"

        # 低波动震荡
        price_range = (np.max(recent_closes) - np.min(recent_closes)) / np.mean(recent_closes) * 100
        if price_range < 2.0:
            score += 0.1  # 可能蓄力

        # 多次转折 = 震荡市，信号弱化
        if turns >= 4:
            score *= 0.5

        return max(-1.0, min(1.0, score))

    def _analyze_turnover(self, closes: np.ndarray,
                          volumes: np.ndarray) -> float:
        """分析成交活跃度"""
        if len(volumes) < 5 or len(closes) < 5:
            return 0.0

        # 近期平均成交量 vs 更早期平均
        recent_avg = float(np.mean(volumes[-5:]))
        earlier_avg = float(np.mean(volumes[-15:-5])) if len(volumes) >= 15 else recent_avg

        if earlier_avg == 0:
            return 0.0

        turnover_change = (recent_avg - earlier_avg) / earlier_avg

        # 成交量放大 + 价格稳定或微涨 = 主力可能建仓
        price_stable = abs(closes[-1] - closes[-5]) / closes[-5] < 0.02

        if turnover_change > 0.5 and price_stable:
            return 0.25
        elif turnover_change > 0.5 and not price_stable:
            return -0.1  # 异常放量但价格不稳
        elif turnover_change < -0.3:
            return -0.15  # 显著缩量

        return 0.0
