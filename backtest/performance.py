"""
回测绩效计算器 (Performance Metrics)
计算策略回测的关键绩效指标

指标列表：
  - 年化收益率 (Annualized Return)
  - 最大回撤 (Maximum Drawdown)
  - Sharpe比率 (Sharpe Ratio, 年化)
  - 胜率 (Win Rate)
  - 盈亏比 (Profit Factor)
  - Calmar比率 (Calmar Ratio)
  - 日均交易次数
  - 单笔最大盈利/亏损
"""
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """回测绩效指标计算器"""

    # 无风险利率（年化，用于Sharpe）
    RISK_FREE_RATE = 0.03  # 3%

    def calculate(self,
                   equity_curve: List[float],
                   trades: List[dict] = None) -> dict:
        """
        计算全部绩效指标

        Args:
            equity_curve: 每日权益净值序列 [初始资金, day1, day2, ...]
            trades: 交易记录列表（可选）

        Returns:
            包含所有指标的字典
        """
        if not equity_curve or len(equity_curve) < 2:
            return self._empty_result()

        arr = np.array(equity_curve, dtype=float)

        # ---- 基础收益 ----
        initial = float(arr[0])
        final = float(arr[-1])
        total_return = (final - initial) / initial if initial > 0 else 0

        n_days = len(arr) - 1
        annual_return = total_return * (252 / max(n_days, 1))

        # ---- 最大回撤 ----
        peak = np.maximum.accumulate(arr)
        drawdown = (arr - peak) / peak
        max_drawdown = abs(np.min(drawdown))
        max_drawdown_date = int(np.argmin(drawdown))

        # ---- 日收益率序列 ----
        daily_returns = np.diff(arr) / arr[:-1]
        daily_returns = daily_returns[np.isfinite(daily_returns)]

        # ---- Sharpe比率 ----
        if len(daily_returns) > 5 and np.std(daily_returns) > 0:
            sharpe = (
                (np.mean(daily_returns) * 252 - self.RISK_FREE_RATE)
                / (np.std(daily_returns) * np.sqrt(252))
            )
        else:
            sharpe = 0.0

        # ---- 交易统计 ----
        trade_stats = self._calc_trade_stats(trades) if trades else {}

        # ---- Calmar比率 ----
        calmar = annual_return / abs(max_drawdown) if abs(max_drawdown) > 1e-8 else 0

        result = {
            # 收益类
            "total_return_pct": round(total_return * 100, 2),
            "annual_return_pct": round(annual_return * 100, 2),
            "final_equity": round(final, 2),

            # 风险类
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "calmar_ratio": round(calmar, 2),
            "volatility_annual": round(
                np.std(daily_returns) * np.sqrt(252) * 100, 2
            ) if len(daily_returns) > 1 else 0,

            # 时间类
            "trading_days": n_days,

            # 回撤详情
            "max_dd_date_idx": max_drawdown_date,

            **trade_stats,
        }

        logger.info(f"绩效计算: 年化={annual_return:.1%}, "
                     f"最大回撤={max_drawdown:.1%}, "
                     f"Sharpe={sharpe:.2f}")
        return result

    def _calc_trade_stats(self, trades: List[dict]) -> dict:
        """计算交易相关统计"""
        if not trades:
            return {}

        pnls = [t.get("pnl", 0) for t in trades if t.get("pnl") is not None]
        if not pnls:
            return {"total_trades": len(trades)}

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 1
        profit_factor = sum(wins) / sum(losses) if sum(losses) > 0 else float('inf')
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0

        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "total_pnl": round(sum(pnls), 2),
        }

    @staticmethod
    def _empty_result() -> dict:
        return {
            "total_return_pct": 0, "annual_return_pct": 0,
            "final_equity": 0, "max_drawdown_pct": 0,
            "sharpe_ratio": 0, "calmar_ratio": 0,
            "volatility_annual": 0, "trading_days": 0,
        }

    def grade(self, metrics: dict) -> str:
        """给策略评级 A/B/C/D/F"""
        sharpe = metrics.get("sharpe_ratio", 0)
        mdd = abs(metrics.get("max_drawdown_pct", 0) / 100)
        win_rate = metrics.get("win_rate", 0)

        score = 0
        if sharpe >= 2.0: score += 30
        elif sharpe >= 1.5: score += 24
        elif sharpe >= 1.0: score += 18
        elif sharpe >= 0.5: score += 10
        elif sharpe > 0: score += 4

        if mdd <= 0.05: score += 25
        elif mdd <= 0.10: score += 20
        elif mdd <= 0.20: score += 12
        elif mdd <= 0.30: score += 5

        if win_rate >= 0.60: score += 20
        elif win_rate >= 0.55: score += 15
        elif win_rate >= 0.50: score += 10
        elif win_rate >= 0.40: score += 5

        if metrics.get("profit_factor", 0) >= 2.5: score += 15
        elif metrics.get("profit_factor", 0) >= 2.0: score += 11
        elif metrics.get("profit_factor", 0) >= 1.5: score += 7
        elif metrics.get("profit_factor", 0) >= 1.0: score += 3

        if score >= 80: return "A (优秀)"
        elif score >= 65: return "B (良好)"
        elif score >= 50: return "C (一般)"
        elif score >= 35: return "D (较差)"
        else: return "F (不可用)"
