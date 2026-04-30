"""
事件驱动回测引擎

完整的回测框架，模拟实盘交易流程：
    历史数据 → 策略信号 → 风控检查 → 成本计算 → 成交 → 绩效评估

支持：
- T+1约束执行
- 完整交易成本建模
- 多股票独立仓位跟踪
- 权益曲线记录
- 绩效指标计算
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Callable

from backtest.cost_model import CostModel
from backtest.t1_constraint import T1Constraint
from backtest.performance import PerformanceMetrics
from backtest.data_loader import HistoricalDataLoader

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    事件驱动回测引擎。

    对于每根日线K线：
    1. 模拟"实时行情"（使用当日收盘价）
    2. 生成过去N根K线作为历史数据
    3. 调用策略引擎生成信号
    4. 风控检查
    5. 执行交易（含成本）
    6. T+1约束检查
    7. 记录权益曲线
    """

    def __init__(self, strategy_func: Callable = None,
                 cost_model: CostModel = None,
                 initial_capital: float = 100000):
        """
        Args:
            strategy_func: 策略函数，签名: (klines, quote) -> Signal or None
                         如果为None，使用内置简单策略
            cost_model: 交易成本模型
            initial_capital: 初始资金
        """
        self.strategy_func = strategy_func
        self.cost = cost_model or CostModel()
        self.initial_capital = initial_capital

        # 回测状态
        self.capital = initial_capital
        self.trades: List[dict] = []
        self.equity_curve: List[Tuple] = []
        self.daily_returns: List[float] = []

        # T+1约束
        self.t1 = T1Constraint()

        # 多股票仓位跟踪
        self.positions: Dict[str, dict] = {}  # code -> {"shares": int, "cost": float}

    def run(self, code: str, start_date: str, end_date: str,
            lookback: int = 60, base_shares: int = 0,
            base_cost: float = 0.0, t_shares: int = 2400) -> dict:
        """
        运行回测。

        Args:
            code: 股票代码
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            lookback: 策略回看K线数量（默认60根）
            base_shares: 底仓股数（做T用）
            base_cost: 底仓成本价
            t_shares: T仓位最大股数

        Returns:
            回测绩效结果字典
        """
        logger.info(f"开始回测: {code} {start_date} ~ {end_date}, "
                   f"资金={self.initial_capital}, T仓上限={t_shares}")

        # 加载历史数据（多加载lookback天用于初始化指标）
        extended_start = (
            datetime.strptime(start_date, "%Y-%m-%d") -
            timedelta(days=int(lookback * 1.5))
        ).strftime("%Y-%m-%d")

        df = HistoricalDataLoader.load_daily(code, extended_start, end_date)
        if df is None or len(df) == 0:
            logger.error(f"无法加载历史数据: {code}")
            return {"error": "No data loaded"}

        klines_all = HistoricalDataLoader.dataframe_to_klines(df)
        dates_all = df["date"].tolist() if "date" in df.columns else [
            f"Day-{i}" for i in range(len(klines_all))
        ]

        # 初始化底仓
        if base_shares > 0 and base_cost > 0:
            base_value = base_shares * base_cost
            self.capital -= base_value
            self.positions[code] = {
                "shares": base_shares,
                "cost": base_cost,
                "type": "base"
            }

        # 主回测循环
        start_idx = max(0, lookback)
        for i in range(start_idx, len(klines_all)):
            date = dates_all[i] if i < len(dates_all) else f"Day-{i}"
            current = klines_all[i]
            close_price = current["close"]

            # 构建历史K线窗口
            hist_klines = klines_all[max(0, i - lookback):i + 1]

            # 构建模拟行情
            quote = {
                "code": code,
                "price": close_price,
                "open": current["open"],
                "high": current["high"],
                "low": current["low"],
                "close": close_price,
                "volume": current["volume"],
                "change_pct": ((close_price - klines_all[i - 1]["close"])
                               / klines_all[i - 1]["close"] * 100)
                if i > 0 else 0,
            }

            # 策略信号生成
            signal = None
            if self.strategy_func:
                try:
                    signal = self.strategy_func(code, hist_klines, quote)
                except Exception as e:
                    logger.debug(f"策略信号生成失败 Day-{i}: {e}")
            else:
                signal = self._default_strategy(code, hist_klines, quote, t_shares)

            # 执行信号
            if signal:
                self._execute_backtest_signal(
                    code, signal, close_price, t_shares
                )

            # 计算当日权益
            equity = self._calc_equity(code, close_price)
            self.equity_curve.append((date, equity))

        # 日终：T+1重置
        # (T1Constraint.reset_day会在每次can_sell时自动调用)

        # 计算绩效指标
        perf = PerformanceMetrics()
        equity_values = [e for _, e in self.equity_curve]
        metrics = perf.calculate(equity_values, self.trades)
        metrics["grade"] = perf.grade(metrics)
        metrics["code"] = code
        metrics["start_date"] = start_date
        metrics["end_date"] = end_date
        metrics["initial_capital"] = self.initial_capital

        logger.info(f"回测完成: {code} | 等级={metrics.get('grade', 'N/A')} | "
                   f"年化={metrics.get('annual_return_pct', 0):.2f}% | "
                   f"回撤={metrics.get('max_drawdown_pct', 0):.2f}% | "
                   f"Sharpe={metrics.get('sharpe_ratio', 0):.2f} | "
                   f"胜率={metrics.get('win_rate', 0):.2%} | "
                   f"交易={metrics.get('total_trades', 0)}次")

        return metrics

    def _default_strategy(self, code: str, klines: list, quote: dict,
                           t_shares: int) -> Optional[dict]:
        """
        内置简单做T策略（用于无外部策略时的演示回测）。

        策略逻辑：
        - 价格跌破5日均线1%以上且RSI<30 → 买入
        - 价格突破5日均线1%以上且RSI>70 → 卖出
        """
        if len(klines) < 10:
            return None

        try:
            from strategy.indicators import MA, RSI
        except ImportError:
            return None

        ma5 = MA(klines, 5)
        rsi = RSI(klines, 14)

        if ma5 is None or rsi is None:
            return None

        price = quote["price"]
        change_pct = quote.get("change_pct", 0)

        # T仓位状态
        t_pos = self.positions.get(f"{code}_t")
        t_held = t_pos["shares"] if t_pos else 0
        # T+1: 检查是否可以卖出
        can_sell = t_held
        if t_held > 0:
            _, can_sell = self.t1.can_sell(f"{code}_t", t_held, t_held)

        # 买入条件
        if price < ma5 * 0.99 and rsi < 35 and t_held < t_shares:
            shares = min(100, t_shares - t_held)
            if shares >= 100:
                return {
                    "code": code,
                    "action": "BUY",
                    "shares": shares,
                    "price": price,
                    "reason": f"价格低于MA5({ma5:.2f})且RSI={rsi:.1f}"
                }

        # 卖出条件
        if price > ma5 * 1.01 and rsi > 65 and can_sell >= 100:
            shares = min(can_sell, 100)
            if shares >= 100:
                return {
                    "code": code,
                    "action": "SELL",
                    "shares": shares,
                    "price": price,
                    "reason": f"价格高于MA5({ma5:.2f})且RSI={rsi:.1f}"
                }

        return None

    def _execute_backtest_signal(self, code: str, signal: dict,
                                  price: float, t_shares: int):
        """执行回测中的交易信号。"""
        action = signal["action"]
        shares = signal["shares"]

        # T+1检查
        t_key = f"{code}_t"
        t_pos = self.positions.get(t_key)
        t_held = t_pos["shares"] if t_pos else 0

        if action == "SELL":
            sellable = t_held
            if t_held > 0:
                _, sellable = self.t1.can_sell(t_key, t_held, t_held)
            if shares > sellable:
                shares = max(0, sellable)
            if shares <= 0:
                return

        # 成本计算
        cost = self.cost.calculate(action, price, shares)
        effective_price = cost["effective_price"]

        # 执行
        if action == "BUY":
            if self.capital < price * shares:
                return  # 资金不足

            self.capital -= effective_price * shares + cost["total"]
            self.t1.record_buy(t_key)

            if t_key not in self.positions:
                self.positions[t_key] = {"shares": 0, "cost": 0.0, "type": "t"}

            pos = self.positions[t_key]
            if pos["shares"] == 0:
                pos["cost"] = effective_price
            else:
                total = pos["cost"] * (pos["shares"]) + effective_price * shares
                pos["cost"] = total / (pos["shares"] + shares)
            pos["shares"] += shares

        elif action == "SELL":
            pos = self.positions.get(t_key)
            if not pos or pos["shares"] < shares:
                return

            pnl = (effective_price - pos["cost"]) * shares - cost["total"]
            self.capital += effective_price * shares - cost["total"]
            pos["shares"] -= shares

            if pos["shares"] <= 0:
                pos["shares"] = 0
                pos["cost"] = 0.0

            self.trades.append({
                "code": code,
                "action": action,
                "shares": shares,
                "price": effective_price,
                "pnl": round(pnl, 2),
                "cost": cost["total"],
                "reason": signal.get("reason", ""),
                "date": datetime.now().strftime("%Y-%m-%d"),
            })

    def _calc_equity(self, code: str, current_price: float) -> float:
        """计算当前总权益（现金 + 持仓市值）。"""
        equity = self.capital

        for key, pos in self.positions.items():
            if pos["shares"] > 0:
                if key == code or key == f"{code}_t":
                    equity += pos["shares"] * current_price

        return round(equity, 2)

    def get_equity_curve(self) -> List[Tuple]:
        """获取权益曲线。"""
        return self.equity_curve

    def get_trades(self) -> List[dict]:
        """获取交易记录。"""
        return self.trades

    def reset(self):
        """重置回测引擎状态。"""
        self.capital = self.initial_capital
        self.trades.clear()
        self.equity_curve.clear()
        self.daily_returns.clear()
        self.positions.clear()
        self.t1.reset_day()
        logger.info("回测引擎已重置")
