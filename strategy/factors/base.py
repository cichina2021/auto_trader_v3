"""
因子基类 — 所有量化因子的统一接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class FactorConfig:
    """因子配置"""
    name: str
    weight: float              # 在模型中的权重 (0~1)
    enabled: bool = True       # 是否启用
    params: Dict[str, Any] = None  # 自定义参数

    def __post_init__(self):
        if self.params is None:
            self.params = {}


class FactorBase(ABC):
    """
    量化因子抽象基类

    所有具体因子必须实现 calculate() 方法，返回 FactorResult。
    """

    def __init__(self, config: FactorConfig):
        self.config = config
        self.name = config.name
        self.weight = config.weight
        self.enabled = config.enabled
        self.params = config.params

    @abstractmethod
    def calculate(self, klines: list, **kwargs) -> 'FactorResult':
        """
        计算因子值

        Args:
            klines: K线数据列表 [{open,close,high,low,volume}, ...]
            **kwargs: 额外数据（实时行情、其他周期数据等）

        Returns:
            FactorResult 包含 direction, confidence, details
        """
        pass

    def __repr__(self) -> str:
        return f"Factor({self.name}, w={self.weight:.2f}, {'ON' if self.enabled else 'OFF'})"
