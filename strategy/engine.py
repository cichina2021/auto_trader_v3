"""
策略引擎 v3.0 (Strategy Engine)
系统核心 — 调度因子计算 + 贝叶斯融合 + 多周期共振 → 输出统一交易信号

职责：
1. 接收股票代码和行情数据
2. 获取多周期K线
3. 调度4大因子分别计算
4. 贝叶斯融合因子信号
5. 多周期MACD共振确认趋势
6. 日内时间窗口权重调整
7. 生成最终Signal对象
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from strategy.factors.base import FactorBase, FactorConfig
from strategy.factors.momentum import MomentumFactor
from strategy.factors.volatility import VolatilityFactor
from strategy.factors.volume import VolumeFactor
from strategy.factors.microstructure import MicrostructureFactor
from strategy.bayesian_fusion import BayesianFusion
from strategy.multi_timeframe import MultiTimeframeMACD
from strategy.signals import Signal, FactorResult
from config.strategy_params import (
    FACTOR_WEIGHTS, MIN_CONFIDENCE, MIN_FACTORS_AGREE,
    TIME_WINDOW_RISK_FACTOR,
)

logger = logging.getLogger(__name__)


class StrategyEngine:
    """
    专业级做T策略引擎

    融合4大因子（动量/波动率/量能/微观结构）+
    贝叶斯信号融合 +
    多周期MACD共振 +
    日内时间窗口管理
    """

    def __init__(self):
        # 初始化因子
        self._factors: List[FactorBase] = []
        self._init_factors()

        # 贝叶斯融合器
        self._bayesian = BayesianFusion(
            prior=0.5,
            min_confidence=MIN_CONFIDENCE * 0.8,  # 融合阶段略低，给后续调整空间
        )

        # 多周期分析器
        self._mtf_macd = MultiTimeframeMACD()

        logger.info(f"策略引擎初始化完成: {len(self._factors)}个因子")

    def _init_factors(self):
        """初始化所有因子实例"""
        factor_classes = [
            ("momentum", MomentumFactor),
            ("volatility", VolatilityFactor),
            ("volume", VolumeFactor),
            ("microstructure", MicrostructureFactor),
        ]

        for name, cls in factor_classes:
            weight = FACTOR_WEIGHTS.get(name, 0)
            if weight > 0:
                config = FactorConfig(name=name, weight=weight)
                instance = cls(config)
                self._factors.append(instance)
                logger.info(f"  因子加载: {instance}")

    def evaluate(self, code: str,
                 realtime_quote: dict = None,
                 klines_map: Dict[str, list] = None) -> Signal:
        """
        对单只股票进行完整评估

        Args:
            code: 股票代码
            realtime_quote: 实时行情字典 {price, change_pct, volume, ...}
            klines_map: 各周期K线 {"daily": [...], "60m": [...], "15m": [...], "5m": [...]}

        Returns:
            Signal 对象（包含方向、价格、数量、置信度、原因等）
        """
        start_time = datetime.now()
        default_klines_map = {}

        try:
            # ---- 数据准备 ----
            if klines_map is None or not klines_map:
                from data.datasource import DataSourceManager
                ds = DataSourceManager()

                daily_kl = ds.get_kline(code, "daily", count=80)
                m60_kl = ds.get_kline(code, "60m", count=60)
                m15_kl = ds.get_kline(code, "15m", count=48)
                m5_kl = ds.get_kline(code, "5m", count=120)

                klines_map = {
                    "daily": self._df_to_list(daily_kl),
                    "60m": self._df_to_list(m60_kl),
                    "15m": self._df_to_list(m15_kl),
                    "5m": self._df_to_list(m5_kl),
                }

            # 使用日线作为主K线进行因子计算
            primary_klines = klines_map.get("daily", [])

            if not primary_klines:
                return Signal(
                    code=code, action="HOLD", price=0, shares=0,
                    confidence=0, reason="无K线数据", strategy="engine",
                    risk_level="LOW",
                )

            current_price = (realtime_quote.get("price") or 0) or \
                           (primary_klines[-1]["close"] if primary_klines else 0)

            # ---- Step 1: 计算4大因子 ----
            factor_results: List[FactorResult] = []
            for factor in self._factors:
                try:
                    fr = factor.calculate(
                        primary_klines,
                        realtime=realtime_quote or {},
                        code=code,
                    )
                    factor_results.append(fr)
                except Exception as e:
                    logger.error(f"因子{factor.name}计算失败: {e}")
                    factor_results.append(FactorResult(
                        factor.name, 0, 0.0, {"error": str(e)}
                    ))

            # ---- Step 2: 贝叶斯融合 ----
            fusion_result = self._bayesian.fuse(factor_results)

            # ---- Step 3: 多周期MACD共振 ----
            mt_result = self._mtf_macd.analyze(klines_map)
            mt_direction = mt_result["direction"]
            mt_confidence = mt_result["confidence"]
            mt_boost = mt_result.get("boost_factor", 1.0)

            # ---- Step 4: 时间窗口调整 ----
            from data.datasource import DataSourceManager as DSM
            time_window = DSM.get_current_time_window()
            tw_factor = TIME_WINDOW_RISK_FACTOR.get(time_window, 1.0)

            # 尾盘窗口只允许卖出（平仓）
            force_sell_only = False
            if time_window == "close" and fusion_result["direction"] > 0:
                fusion_result["direction"] = 0
                fusion_result["confidence"] *= 0.3
                force_sell_only = True

            # ---- Step 5: 综合决策 ----
            # 基础置信度 = 贝叶斯后验 × 时间窗口因子 × MTF增强
            base_confidence = fusion_result["confidence"] * tw_factor * mt_boost
            base_confidence = min(1.0, base_confidence)

            # 方向判断：贝叶斯为主，MTF为辅（当MTF强共振时可翻转弱信号）
            final_dir = fusion_result["direction"]

            # MTF全共振且与贝叶斯冲突时，降低置信度但不反转方向
            # （保守策略：不轻易被短周期反转）
            if mt_result["resonance_level"] == "full" and \
               mt_direction != final_dir and mt_direction != 0:
                base_confidence *= 0.6  # 冲突降权

            # ---- Step 6: 确定是否触发 ----
            should_trigger, trigger_reason = self._bayesian.should_trigger({
                "direction": final_dir,
                "confidence": base_confidence,
                "agreement": fusion_result["agreement"],
            }, min_agree=MIN_FACTORS_AGREE)

            if not should_trigger:
                return Signal(
                    code=code, action="HOLD", price=current_price, shares=0,
                    confidence=base_confidence, reason=trigger_reason,
                    strategy="engine_v3",
                    factors={fr.name: fr.to_dict() for fr in factor_results},
                    risk_level="LOW",
                )

            action = "BUY" if final_dir > 0 else "SELL"

            # ---- Step 7: 风险等级评估 ----
            risk_level = self._assess_risk_level(base_confidence, mt_result)

            # ---- Step 8: 生成原因描述 ----
            reasons_parts = [trigger_reason]
            if mt_result["resonance_level"] != "mixed":
                reasons_parts.append(f"多周期:{mt_result['summary']}")
            reasons_parts.append(f"时间窗:{time_window}(×{tw_factor})")
            reason_str = " | ".join(reasons_parts)

            # 计算建议数量（由风控层最终决定，这里给出参考值）
            suggested_shares = self._calc_suggested_shares(
                code, action, current_price, factor_results
            )

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(f"[{code}] 策略评估完成: {action} "
                         f"@{current_price:.2f} 置信={base_confidence:.0%} "
                         f"({elapsed_ms:.0f}ms)")

            return Signal(
                code=code,
                action=action,
                price=current_price,
                shares=suggested_shares,
                confidence=base_confidence,
                reason=reason_str,
                strategy="engine_v3_bayesian_mtf",
                factors={
                    "fusion": fusion_result,
                    "mtf": mt_result,
                    **{fr.name: fr.to_dict() for fr in factor_results},
                },
                risk_level=risk_level,
            )

        except Exception as e:
            logger.error(f"[{code}] 策略引擎异常: {e}", exc_info=True)
            return Signal(
                code=code, action="HOLD", price=0, shares=0,
                confidence=0, reason=f"引擎异常: {str(e)}", strategy="error",
                risk_level="HIGH",
            )

    def evaluate_batch(self, codes: List[str],
                       realtime_quotes: Dict[str, dict] = None) -> List[Signal]:
        """
        批量评估多只股票

        Returns:
            按置信度排序的信号列表
        """
        signals = []
        for code in codes:
            quote = (realtime_quotes or {}).get(code)
            sig = self.evaluate(code, realtime_quote=quote)
            if sig.action != "HOLD":
                signals.append(sig)

        # 按置信度降序排列
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    @staticmethod
    def _df_to_list(df) -> list:
        """将pandas DataFrame转为K线列表"""
        if df is None or len(df) == 0:
            return []

        records = []
        for _, row in df.iterrows():
            try:
                records.append({
                    "open": float(row.get("open", 0)),
                    "close": float(row.get("close", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "volume": float(row.get("volume", 0)),
                    "date": str(row.get("date", "")),
                })
            except (ValueError, TypeError):
                continue
        return records

    @staticmethod
    def _assess_risk_level(confidence: float,
                           mt_result: dict) -> str:
        """评估信号风险等级"""
        if confidence >= 0.85 and mt_result["resonance_level"] == "full":
            return "HIGH"   # 高置信+强共振 = 高风险操作（仓位需谨慎）
        elif confidence >= 0.70:
            return "MEDIUM"
        else:
            return "LOW"

    @staticmethod
    def _calc_suggested_shares(code: str, action: str,
                                price: float,
                                factor_results: list) -> int:
        """
        计算建议做T股数

        注意：实际仓位由RiskManager的Kelly公式决定，
        这里仅返回一个基于配置的基础参考值。
        最终shares在执行前会被RiskManager覆盖。
        """
        from config.settings import POSITIONS
        pos_config = POSITIONS.get(code)
        if pos_config:
            t_shares = pos_config.get("t_shares", 2400)
            # 根据信号强度调整比例
            return max(100, int(t_shares))  # 至少100股（1手）
        return 0  # 未配置该股票则返回0
