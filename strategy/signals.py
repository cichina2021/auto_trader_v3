"""
策略信号数据类
定义系统中所有交易信号的数据结构
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Signal:
    """
    交易信号

    Attributes:
        code: 股票代码（如 "002539"）
        action: 交易方向 'BUY' / 'SELL' / 'HOLD'
        price: 建议价格
        shares: 建议数量
        confidence: 综合置信度 (0.0 ~ 1.0)
        reason: 信号原因描述（可展示给用户）
        strategy: 产生此信号的策略名称
        timestamp: 信号时间戳
        factors: 各因子得分明细 {factor_name: score}
        risk_level: 风险等级 "LOW" / "MEDIUM" / "HIGH"
    """
    code: str
    action: str                    # 'BUY' / 'SELL' / 'HOLD'
    price: float
    shares: int
    confidence: float              # 0.0 ~ 1.0
    reason: str
    strategy: str
    timestamp: datetime = field(default_factory=datetime.now)
    factors: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "MEDIUM"     # LOW / MEDIUM / HIGH

    @property
    def is_buy(self) -> bool:
        return self.action == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.action == "SELL"

    @property
    def is_strong(self) -> bool:
        """是否为强信号（置信度>=80%）"""
        return self.confidence >= 0.80

    def to_dict(self) -> dict:
        """转为字典（用于JSON序列化/HTTP响应）"""
        return {
            "code": self.code,
            "action": self.action,
            "price": round(self.price, 3),
            "shares": self.shares,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "strategy": self.strategy,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "factors": self.factors,
            "risk_level": self.risk_level,
        }

    def __repr__(self) -> str:
        direction = "买↑" if self.is_buy else ("卖↓" if self.is_sell else "观望")
        return (
            f"Signal({self.code} {direction} @{self.price:.2f} "
            f"x{self.shares} 置信{self.confidence:.0%} [{self.strategy}]"
        )


@dataclass
class FactorResult:
    """
    因子计算结果

    Attributes:
        name: 因子名称（如 "momentum", "volatility"）
        direction: 方向 +1(看多) / -1(看空) / 0(中性)
        confidence: 该因子的置信度 (0.0 ~ 1.0)
        details: 详细数据（各子指标得分、原始值等）
        weight: 该因子在模型中的权重
    """
    name: str
    direction: int                 # 1 / -1 / 0
    confidence: float              # 0.0 ~ 1.0
    details: Dict[str, Any] = field(default_factory=dict)
    weight: float = 0.0

    @property
    def weighted_score(self) -> float:
        """加权得分 = 方向 × 置信度 × 权重"""
        return self.direction * self.confidence * self.weight

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "weight": self.weight,
            "weighted_score": round(self.weighted_score, 4),
            "details": self.details,
        }


@dataclass
class TradeRecord:
    """
    交易记录

    用于风控跟踪和绩效统计
    """
    code: str
    action: str                   # 'BUY' / 'SELL'
    price: float
    shares: int
    amount: float                  # 成交金额
    commission: float              # 手续费
    timestamp: datetime = field(default_factory=datetime.now)
    signal_confidence: float = 0.0 # 触发信号的置信度
    strategy: str = ""             # 触发策略
    pnl: Optional[float] = None    # 盈亏（卖出时计算）
    pnl_pct: Optional[float] = None # 盈亏百分比

    def to_dict(self) -> dict:
        d = {
            "code": self.code,
            "action": self.action,
            "price": round(self.price, 3),
            "shares": self.shares,
            "amount": round(self.amount, 2),
            "commission": round(self.commission, 2),
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": self.strategy,
            "signal_confidence": round(self.signal_confidence, 4),
        }
        if self.pnl is not None:
            d["pnl"] = round(self.pnl, 2)
            d["pnl_pct"] = round(self.pnl_pct, 4)
        return d
