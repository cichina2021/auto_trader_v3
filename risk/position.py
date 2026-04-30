"""
仓位管理与ATR动态止损
"""
import logging
from typing import Optional, Dict
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class PositionManager:
    """仓位管理器 — ATR动态止损 + 仓位跟踪"""

    def __init__(self,
                 atr_multiplier: float = 2.0,
                 tp_multiplier: float = 3.0,
                 fixed_stop_pct: float = 0.025,
                 fixed_tp_pct: float = 0.03):
        self.atr_mult_sl = atr_multiplier
        self.atr_mult_tp = tp_multiplier
        self.fixed_stop_pct = fixed_stop_pct
        self.fixed_tp_pct = fixed_tp_pct

        # 持仓记录：{code -> {entry_price, shares, entry_time, stop_loss, take_profit}}
        self._positions: Dict[str, dict] = {}

    def open_position(self, code: str, price: float, shares: int,
                      action: str) -> dict:
        """
        开仓（或调整做T仓位）

        Returns:
            包含止损/止盈价的仓位信息字典
        """
        now = datetime.now()

        # 计算动态止损止盈（使用固定百分比作为后备）
        if action == "BUY":
            stop_loss = price * (1 - self.fixed_stop_pct)
            take_profit = price * (1 + self.fixed_tp_pct)
        else:  # SELL (逆T)
            stop_loss = price * (1 + self.fixed_stop_pct)
            take_profit = price * (1 - self.fixed_tp_pct)

        position_info = {
            "code": code,
            "entry_price": round(price, 3),
            "shares": shares,
            "action": action,
            "entry_time": now,
            "stop_loss": round(stop_loss, 3),
            "take_profit": round(take_profit, 3),
            "highest_price": price,   # 跟踪最高价（用于移动止损）
            "lowest_price": price,    # 跟踪最低价
            "pnl": 0.0,
            "pnl_pct": 0.0,
        }

        self._positions[code] = position_info

        logger.info(f"[{code}] 开仓: {action} {shares}股 @ {price:.2f}, "
                     f"止损={stop_loss:.2f}, 止盈={take_profit:.2f}")
        return position_info

    def update_with_atr(self, code: str, atr: float):
        """用ATR更新某持仓的动态止损"""
        pos = self._positions.get(code)
        if not pos or atr <= 0:
            return

        entry = pos["entry_price"]
        action = pos["action"]

        if action == "BUY":
            new_sl = entry - (atr * self.atr_mult_sl)
            new_tp = entry + (atr * self.atr_mult_tp)
        else:
            new_sl = entry + (atr * self.atr_mult_sl)
            new_tp = entry - (atr * self.atr_mult_tp)

        pos["stop_loss"] = max(pos["stop_loss"], round(new_sl, 3)) \
            if action == "BUY" else min(pos["stop_loss"], round(new_sl, 3))
        pos["take_profit"] = round(new_tp, 3)

        logger.debug(f"[{code}] ATR动态止损更新: SL={pos['stop_loss']:.2f}, "
                      f"TP={pos['take_profit']:.2f}, ATR={atr:.3f}")

    def check_exit_signal(self, code: str, current_price: float) -> tuple:
        """
        检查是否触发止损/止盈/移动止损

        Returns:
            (should_exit: bool, reason: str, exit_type: str)
        """
        pos = self._positions.get(code)
        if not pos:
            return False, "", ""

        action = pos["action"]
        sl = pos["stop_loss"]
        tp = pos["take_profit"]
        entry = pos["entry_price"]

        # 更新追踪高低点
        pos["highest_price"] = max(pos["highest_price"], current_price)
        pos["lowest_price"] = min(pos["lowest_price"], current_price)

        # ---- 止损检查 ----
        if action == "BUY" and current_price <= sl:
            return True, f"触发止损 ({current_price:.2f}<={sl:.2f})", "STOP_LOSS"
        elif action != "BUY" and current_price >= sl:
            return True, f"触发止损 ({current_price:.2f}>={sl:.2f})", "STOP_LOSS"

        # ---- 止盈检查 ----
        if action == "BUY" and current_price >= tp:
            return True, f"触发止盈 ({current_price:.2f}>={tp:.2f})", "TAKE_PROFIT"
        elif action != "BUY" and current_price <= tp:
            return True, f"触发止盈 ({current_price:.2f}<={tp:.2f})", "TAKE_PROFIT"

        # ---- 移动止损（保住利润）----
        if action == "BUY" and pos["highest_price"] > entry * 1.02:
            trailing_sl = pos["highest_price"] * 0.98  # 从最高点回撤2%
            if current_price < trailing_sl:
                return True, f"移动止损 (从高点{pos['highest_price']:.2f})", "TRAILING_STOP"

        return False, "", ""

    def close_position(self, code: str, exit_price: float,
                       exit_type: str = "MANUAL") -> Optional[dict]:
        """平仓并返回结算信息"""
        pos = self._positions.get(code)
        if not pos:
            return None

        entry = pos["entry_price"]
        shares = pos["shares"]
        action = pos["action"]

        if action == "BUY":
            pnl = (exit_price - entry) * shares
        else:
            pnl = (entry - exit_price) * shares

        pnl_pct = (exit_price - entry) / entry * 100 if entry > 0 else 0
        if action != "BUY":
            pnl_pct = -pnl_pct

        settlement = {
            **pos,
            "exit_price": round(exit_price, 3),
            "exit_type": exit_type,
            "exit_time": datetime.now(),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 4),
            "holding_seconds": int((datetime.now() - pos["entry_time"]).total_seconds()),
        }

        del self._positions[code]

        logger.info(
            f"[{code}] 平仓: {exit_type} @{exit_price:.2f}, "
            f"PnL={pnl:+.2f}({pnl_pct:+.2f}%)"
        )
        return settlement

    def get_position(self, code: str) -> Optional[dict]:
        """获取当前持仓"""
        return self._positions.get(code)

    def get_all_positions(self) -> Dict[str, dict]:
        """获取所有持仓快照"""
        return dict(self._positions)

    def has_open_position(self, code: str) -> bool:
        return code in self._positions

    def unrealized_pnl(self, code: str, current_price: float) -> tuple:
        """计算未实现盈亏 (pnl, pnl_pct)"""
        pos = self._positions.get(code)
        if not pos or current_price <= 0:
            return 0.0, 0.0

        entry = pos["entry_price"]
        shares = pos["shares"]
        action = pos["action"]

        if action == "BUY":
            pnl = (current_price - entry) * shares
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl = (entry - current_price) * shares
            pnl_pct = (entry - current_price) / entry * 100
            pnl_pct = -pnl_pct

        return round(pnl, 2), round(pnl_pct, 4)
