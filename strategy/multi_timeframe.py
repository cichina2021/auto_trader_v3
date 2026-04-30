"""
多周期MACD共振模块 (Multi-Timeframe MACD Resonance)
通过日线/60m/15m/5m四个周期的MACD信号共振确认趋势

权重分配：
  日线(40%) → 大方向
  60分钟(30%) → 中期趋势
  15分钟(20%) → 短期动量  
  5分钟(10%) → 精确入场

全部周期同向 = 强信号（置信度大幅提升）
"""
import logging
from typing import Dict, Optional, List
from strategy.indicators import MACD, KDJ
from config.strategy_params import MULTI_TF_WEIGHTS

logger = logging.getLogger(__name__)


class MultiTimeframeMACD:
    """多周期MACD共振分析器"""

    # 周期配置：(名称, K线数据key, MACD参数)
    TIMEFRAMES = {
        "daily":  {"period": "daily", "fast": 12, "slow": 26, "signal": 9},
        "60m":    {"period": "60m",   "fast": 12, "slow": 26, "signal": 9},
        "15m":    {"period": "15m",   "fast": 12, "slow": 26, "signal": 9},
        "5m":     {"period": "5m",    "fast": 6,  "slow": 13, "signal": 5},
    }

    def __init__(self):
        self.weights = MULTI_TF_WEIGHTS

    def analyze(self,
                klines_map: Dict[str, list]) -> dict:
        """
        分析多周期MACD共振状态

        Args:
            klines_map: 各周期K线数据 {"daily": [...], "60m": [...], ...}

        Returns:
            {
                "direction": 1 / -1 / 0,
                "confidence": 0~1,
                "resonance_level": "full" / "partial" / "mixed" / "none",
                "timeframes": {各周期的详细结果},
                "summary": 文字描述,
            }
        """
        tf_results = {}
        bullish_count = 0
        bearish_count = 0
        total_weighted_score = 0.0
        total_weight_used = 0.0

        for tf_name, tf_config in self.TIMEFRAMES.items():
            klines = klines_map.get(tf_name)
            if not klines or len(klines) < 40:
                tf_results[tf_name] = {
                    "available": False, "direction": 0, "confidence": 0,
                    "reason": "数据不足",
                }
                continue

            macd_data = MACD(klines,
                             fast=tf_config["fast"],
                             slow=tf_config["slow"],
                             signal=tf_config["signal"])

            kdj_data = KDJ(klines)

            direction, conf, details = self._eval_tf_signal(
                tf_name, macd_data, kdj_data
            )

            weight = self.weights.get(tf_name, 0)
            tf_results[tf_name] = {
                "available": True,
                "direction": direction,
                "confidence": round(conf, 4),
                "weight": weight,
                **details,
            }

            if direction > 0:
                bullish_count += 1
                total_weighted_score += weight * conf
            elif direction < 0:
                bearish_count += 1
                total_weighted_score -= weight * conf
            total_weight_used += weight

        # ---- 共振级别判断 ----
        if bullish_count == 4 and bearish_count == 0:
            resonance_level = "full"
            confidence_boost = 1.3      # 全部看多，大幅增强
        elif bearish_count == 4 and bullish_count == 0:
            resonance_level = "full"
            confidence_boost = 1.3
        elif bullish_count >= 3 and bearish_count == 0:
            resonance_level = "strong_bullish"
            confidence_boost = 1.15
        elif bearish_count >= 3 and bullish_count == 0:
            resonance_level = "strong_bearish"
            confidence_boost = 1.15
        elif bullish_count >= 2 and bearish_count <= 1:
            resonance_level = "partial_bullish"
            confidence_boost = 1.05
        elif bearish_count >= 2 and bullish_count <= 1:
            resonance_level = "partial_bearish"
            confidence_boost = 1.05
        else:
            resonance_level = "mixed"
            confidence_boost = 0.7       # 混乱，削弱信号

        # ---- 综合方向与置信度 ----
        if total_weight_used > 0:
            base_confidence = abs(total_weighted_score) / total_weight_used
        else:
            base_confidence = 0.0

        confidence = min(1.0, base_confidence * confidence_boost)

        if total_weighted_score > 0.08:
            direction = 1
        elif total_weighted_score < -0.08:
            direction = -1
        else:
            direction = 0

        # ---- 生成文字摘要 ----
        summary_parts = []
        for tf_name in ["daily", "60m", "15m", "5m"]:
            r = tf_results.get(tf_name, {})
            if not r.get("available"):
                summary_parts.append(f"{tf_name}:N/A")
            else:
                arrow = "↑" if r["direction"] > 0 else ("↓" if r["direction"] < 0 else "-")
                summary_parts.append(f"{tf_name}:{arrow}({r['confidence']:.0%})")

        result = {
            "direction": direction,
            "confidence": round(confidence, 4),
            "resonance_level": resonance_level,
            "boost_factor": round(confidence_boost, 2),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "timeframes": tf_results,
            "weighted_score": round(total_weighted_score, 4),
            "summary": f"[{resonance_level}] {' | '.join(summary_parts)}",
        }

        logger.debug(f"多周期MACD: {result['summary']}")
        return result

    def _eval_tf_signal(self, tf_name: str,
                         macd_data: dict,
                         kdj_data: dict) -> tuple[int, float, dict]:
        """
        评估单个周期的信号方向和置信度

        Returns:
            (方向, 置信度, 详情字典)
        """
        if not macd_data or macd_data.get("macd") is None:
            return 0, 0.0, {"reason": "无MACD数据"}

        hist = macd_data.get("histogram", 0)
        cross = macd_data.get("cross")
        macd_val = macd_data.get("macd", 0)

        score = 0.0
        reasons = []

        # MACD柱状图方向
        if hist > 0:
            score += min(0.5, hist / 0.03)
            reasons.append(f"DIF+")
        elif hist < 0:
            score -= min(0.5, abs(hist) / 0.03)
            reasons.append(f"DIF-")

        # 金叉死叉
        if cross == "golden":
            score += 0.35
            reasons.append("金叉")
        elif cross == "dead":
            score -= 0.35
            reasons.append("死叉")

        # MACD线在零轴上方/下方
        if macd_val > 0:
            score += 0.15
        elif macd_val < 0:
            score -= 0.15

        # KDJ辅助确认（仅日线和60分钟参考）
        if tf_name in ("daily", "60m") and kdj_data.get("k") is not None:
            k_val = kdj_data["k"]
            d_val = kdj_data["d"]
            j_val = kdj_data["j"]
            signal = kdj_data.get("signal")

            if signal == "oversold":
                score += 0.1
                reasons.append(f"KDJ超卖(K={k_val:.0f})")
            elif signal == "overbought":
                score -= 0.1
                reasons.append(f"KDJ超买(K={k_val:.0f})")

        # 归一化到[-1, 1]
        score = max(-1.0, min(1.0, score))
        confidence = abs(score)

        direction = 1 if score > 0.05 else (-1 if score < -0.05 else 0)

        return direction, round(confidence, 4), {
            "macd_hist": round(hist, 4),
            "cross": cross,
            "score": round(score, 3),
            "reasons": reasons,
        }
