"""
风控管理器 (Risk Manager) v3.0
整合Kelly仓位 + VaR风控 + ATR止损 + 限额检查的统一入口

这是所有交易信号的必经关卡 — 任何信号在执行前必须通过RiskManager检查。
"""
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from risk.kelly import KellyCalculator
from risk.var import VaRCalculator
from risk.position import PositionManager
from risk.limits import LimitsChecker
from strategy.signals import Signal, TradeRecord
from config.risk_params import INITIAL_CAPITAL

logger = logging.getLogger(__name__)


class RiskManager:
    """
    专业级风控管理器

    四层防护：
    Layer 0: 熔断器（连续亏损/日亏损超限 → 暂停所有交易）
    Layer 1: 日亏损限额（3%硬停 / 1.5%警告）
    Layer 2: 仓位限额（单股30% / 总计70%）
    Layer 3: 频率限制（单股4次 / 全局10次）
    Layer 4: Kelly公式动态仓位
    Layer 5: ATR动态止损 / VaR实时监控
    """

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self._initial_capital = initial_capital
        self._equity = initial_capital
        self._trade_history: List[dict] = []

        # 子模块
        self.kelly = KellyCalculator()
        self.var_calc = VaRCalculator()
        self.position_mgr = PositionManager()
        self.limits = LimitsChecker()

        logger.info(f"风控管理器初始化完成 | 初始资金: ¥{initial_capital:,.0f}")

    @property
    def capital(self) -> float:
        """当前权益"""
        return self._equity

    @property
    def is_halted(self) -> bool:
        """系统是否已熔断"""
        return self.limits.get_summary()["halted"]

    @property
    def trade_history(self) -> List[dict]:
        """交易历史"""
        return self._trade_history

    def can_trade(self, code: str, action: str, shares: int,
                  price: float) -> Tuple[bool, str]:
        """
        简化版风控检查（供ExecutionManager调用）

        Returns:
            (是否允许, 原因描述)
        """
        return self.limits.can_trade(
            code=code, action=action, shares=shares,
            price=price, equity=self._equity
        )

    def calculate_position_size(self, code: str, price: float) -> int:
        """
        Kelly公式计算最优仓位（供主循环调用）

        Returns:
            建议股数（100的整数倍）
        """
        kelly_result = self.kelly.calculate(self._trade_history)
        shares = self.kelly.calc_shares(
            capital=self._equity * 0.7,
            price=price,
            kelly_result=kelly_result,
        )
        return shares

    def check_and_adjust(self, signal: Signal) -> Tuple[bool, str, Optional[Signal]]:
        """
        对策略引擎产生的信号进行风控审核和调整

        Args:
            signal: 原始信号

        Returns:
            (是否允许执行, 原因描述, 调整后的信号或None)
        """
        if signal.action == "HOLD":
            return True, "观望信号，无需风控", signal

        code = signal.code
        price = signal.price
        action = signal.action

        # ---- 限额检查 ----
        ref_shares = max(signal.shares, 100)

        can_trade, reason = self.limits.can_trade(
            code=code,
            action=action,
            shares=ref_shares,
            price=price,
            equity=self._equity,
        )

        if not can_trade:
            return False, reason, None

        # ---- Kelly动态仓位调整 ----
        kelly_result = self.kelly.calculate(self._trade_history)
        adjusted_shares = self.kelly.calc_shares(
            capital=self._equity * 0.7,
            price=price,
            kelly_result=kelly_result,
            max_shares=signal.shares if signal.shares > 0 else None,
        )

        if adjusted_shares <= 0:
            return False, f"Kelly公式建议不交易 (kelly_f={kelly_result['kelly_fraction']:.3f})", None

        # ---- VaR检查 ----
        var_result = self.var_calc.calculate(
            [t.get("pnl_pct", 0) for t in self._trade_history]
        )
        var_result = self.var_calc.update_with_equity(var_result, self._equity)
        var_ok, var_msg = self.var_calc.check_limit(var_result)

        if not var_ok:
            logger.warning(f"VaR检查未通过: {var_msg}")
            adjusted_shares = int(adjusted_shares * 0.5)
            if adjusted_shares < 100:
                return False, f"VaR超限且调整后仓位不足: {var_msg}", None

        # ---- 构建调整后的信号 ----
        adjusted_signal = Signal(
            code=signal.code,
            action=signal.action,
            price=signal.price,
            shares=adjusted_shares,
            confidence=min(signal.confidence, kelly_result["cap_adjusted"]),
            reason=f"{signal.reason} | Kelly:{adjusted_shares}股({kelly_result['confidence']}级)",
            strategy=f"{signal.strategy}_risk_checked",
            factors={
                **(signal.factors or {}),
                "risk": {
                    "kelly": kelly_result,
                    "var": var_result,
                    "limits": self.limits.get_summary(),
                },
            },
            risk_level="HIGH" if var_result.get("exceeds_warning") else signal.risk_level,
        )

        final_reason = "风控通过"
        if var_msg and var_msg.startswith("⚡"):
            final_reason += f" | {var_msg}"

        return True, final_reason, adjusted_signal

    def record_trade(self, code: str, action: str, shares: int,
                     price: float, pnl: float = 0):
        """
        记录一笔完成的交易（供ExecutionManager调用）

        Args:
            code: 股票代码
            action: BUY/SELL
            shares: 股数
            price: 成交价
            pnl: 盈亏金额
        """
        from backtest.cost_model import CostModel
        cost_model = CostModel()
        cost_info = cost_model.calculate(action, price, shares)
        amount = price * shares

        trade = {
            "code": code,
            "action": action,
            "price": price,
            "shares": shares,
            "amount": amount,
            "commission": cost_info["total_cost"],
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / amount * 100, 4) if amount > 0 else 0,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._trade_history.append(trade)

        # 更新权益
        if pnl is not None:
            self._equity += pnl

        # 同步到LimitsChecker
        self.limits.record_trade(trade)

        # 更新持仓
        if action == "BUY":
            self.position_mgr.open_position(code, price, shares, action)
        elif action == "SELL":
            self.position_mgr.close_position(code, price, "TRADE")

        logger.info(f"[{code}] 交易已记录: "
                    f"{action} x{shares} @{price:.2f}, "
                    f"PnL={pnl:+.2f}, "
                    f"权益=¥{self._equity:,.2f}")

    def get_status(self) -> dict:
        """获取完整风控状态（供Web面板使用）"""
        kelly = self.kelly.calculate(self._trade_history)
        var_data = [t.get("pnl_pct", 0) for t in self._trade_history]
        var_result = self.var_calc.calculate(var_data)
        var_result = self.var_calc.update_with_equity(var_result, self._equity)

        limits = self.limits.get_summary()

        positions = {}
        for code, pos in self.position_mgr.get_all_positions().items():
            positions[code] = {
                **pos,
                "unrealized_pnl": None,
            }

        return {
            "equity": round(self._equity, 2),
            "initial_capital": self._initial_capital,
            "daily_pnl": limits["daily_pnl"],
            "daily_pnl_pct": round(
                limits["daily_pnl"] / self._equity * 100, 2
            ) if self._equity > 0 else 0,
            "total_trades": len(self._trade_history),
            "positions": positions,
            "kelly_fraction": kelly["kelly_fraction"],
            "kelly_confidence": kelly["confidence"],
            "win_rate": kelly["win_rate"],
            "var": var_result,
            "is_halted": limits["halted"],
            "halt_reason": limits["halt_reason"],
            "consecutive_losses": limits["consecutive_losses"],
            "halted": limits["halted"],
        }

    def get_risk_dashboard(self) -> dict:
        """获取完整的风控仪表盘数据"""
        return self.get_status()
