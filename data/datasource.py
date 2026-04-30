"""
统一数据源管理器
多级容错：akshare → 新浪 → 腾讯，自动降级
带TTL缓存 + 频率限制 + 数据校验
"""
import time
import logging
from typing import List, Optional, Dict
from datetime import datetime

import pandas as pd

from config.settings import DATA_SOURCE_PRIORITY, TIME_WINDOWS, TRADE_START, TRADE_END, LUNCH_START, LUNCH_END
from data.cache import DataCache, get_cache, CACHE_TTL_REALTIME, CACHE_TTL_KLINE
from data.validator import validate_quote, validate_kline
from data.akshare_adapter import AkShareAdapter
from data.sina_adapter import SinaAdapter
from data.tencent_adapter import TencentAdapter

logger = logging.getLogger(__name__)


class DataSourceManager:
    """
    统一行情数据源管理器（单例模式）

    职责：
    1. 管理多个数据源适配器（akshare / sina / tencent）
    2. 多源自动降级（主源失败→切换备用源）
    3. TTL缓存管理
    4. 请求频率限制（防止被封IP）
    5. 数据校验与清洗
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 初始化适配器（按优先级排序）
        self._adapters = []
        self._init_adapters()

        # 缓存
        self._cache: DataCache = get_cache()

        # 频率限制（滑动窗口）
        self._request_timestamps: list[float] = []
        self._rate_limit = 60  # 每分钟最多60次请求

        logger.info(f"数据源初始化完成: {[a.NAME for a in self._adapters]}")

    def _init_adapters(self):
        adapter_map = {
            "akshare": AkShareAdapter,
            "sina": SinaAdapter,
            "tencent": TencentAdapter,
        }
        for name in DATA_SOURCE_PRIORITY:
            cls = adapter_map.get(name)
            if cls is not None:
                adapter = cls()
                if adapter.is_available():
                    self._adapters.append(adapter)
                    logger.info(f"  ✓ {adapter.NAME} 可用")
                else:
                    logger.warning(f"  ✗ {adapter.NAME} 不可用")

    # ================================================================
    # 公开接口
    # ================================================================

    def get_realtime(self, codes: List[str]) -> List[dict]:
        """
        获取实时行情（带缓存和降级）

        Args:
            codes: 股票代码列表 ["002539", "600519"]

        Returns:
            校验后的行情列表 [{code, name, price, ...}, ...]
        """
        cache_key = f"rt_{'_'.join(codes)}"

        def _fetch():
            return self._fetch_realtime_from_sources(codes)

        raw_data = self._cache.get(cache_key, CACHE_TTL_REALTIME, _fetch)

        # 校验每条数据
        valid_data = []
        for quote in (raw_data or []):
            ok, reason = validate_quote(quote)
            if ok:
                valid_data.append(quote)
            else:
                logger.debug(f"行情校验不通过[{quote.get('code','?')}]: {reason}")

        return valid_data

    def get_kline(self, code: str, period: str = "daily",
                  count: int = 120) -> Optional[pd.DataFrame]:
        """
        获取K线数据（带缓存和降级）

        Args:
            code: 股票代码
            period: 周期 ("daily" / "60m" / "15m" / "5m")
            count: 条数

        Returns:
            标准化K线 DataFrame 或 None
        """
        cache_key = f"kl_{code}_{period}_{count}"

        def _fetch():
            return self._fetch_kline_from_sources(code, period, count)

        df = self._cache.get(cache_key, CACHE_TTL_KLINE, _fetch)
        if df is not None and len(df) > 0:
            valid, reason = validate_kline(df)
            if not valid:
                logger.warning(f"K线校验失败 [{code}/{period}]: {reason}")
                from data.validator import sanitize_kline
                return sanitize_kline(df)
            return df
        return None

    def get_order_flow(self, code: str) -> dict:
        """获取订单流数据（占位实现）"""
        return {"buy_volume": 0, "sell_volume": 0, "total_volume": 0}

    def invalidate_stock_cache(self, code: str):
        """清除某只股票的所有缓存"""
        self._cache.invalidate_pattern(code)

    # ================================================================
    # 内部方法
    # ================================================================

    def _rate_limited(self) -> bool:
        """检查是否超过频率限制"""
        now = time.time()
        # 清理1分钟前的记录
        self._request_timestamps = [
            t for t in self._request_timestamps if now - t < 60
        ]
        if len(self._request_timestamps) >= self._rate_limit:
            logger.debug("触发频率限制，跳过本次请求")
            return True
        self._request_timestamps.append(now)
        return False

    def _fetch_realtime_from_sources(self, codes: List[str]) -> List[dict]:
        """按优先级依次尝试各数据源获取实时行情"""
        if self._rate_limited():
            return []

        errors = []
        for adapter in self._adapters:
            try:
                result = adapter.get_realtime(codes)
                if result and len(result) > 0:
                    logger.debug(f"实时行情通过{adapter.NAME}获取成功: {len(result)}条")
                    return result
            except Exception as e:
                err_msg = f"{adapter.NAME}: {e}"
                errors.append(err_msg)
                logger.warning(f"{adapter.NAME}获取失败: {e}")

        logger.error(f"所有数据源均无法获取实时行情: {'; '.join(errors)}")
        return []

    def _fetch_kline_from_sources(self, code: str, period: str,
                                    count: int) -> Optional[pd.DataFrame]:
        """按优先级依次尝试各数据源获取K线"""
        if self._rate_limited():
            return None

        for adapter in self._adapters:
            try:
                df = adapter.get_kline(code, period, count)
                if df is not None and len(df) > 0:
                    logger.debug(
                        f"K线通过{adapter.NAME}获取成功 "
                        f"[{code}/{period}]: {len(df)}条"
                    )
                    return df
            except Exception as e:
                logger.warning(f"{adapter.NAME}K线获取失败 [{code}/{period}]: {e}")

        logger.error(f"所有数据源均无法获取K线 [{code}/{period}]")
        return None

    @staticmethod
    def is_trading_time() -> bool:
        """
        判断当前是否在交易时间内

        Returns:
            True: 在交易时间范围内
        """
        now = datetime.now()

        # 周末不交易
        if now.weekday() >= 5:
            return False

        current_time = now.strftime("%H:%M")

        # 上午盘: 09:30 - 11:30
        if TRADE_START <= current_time <= LUNCH_START:
            return True

        # 下午盘: 13:00 - 14:57
        if LUNCH_END <= current_time <= TRADE_END:
            return True

        return False

    @staticmethod
    def get_current_time_window() -> str:
        """
        获取当前所属的日内交易窗口

        Returns:
            "open" | "morning" | "afternoon" | "close" | "non_trading"
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        for window_name, (start, end) in TIME_WINDOWS.items():
            if start <= current_time <= end:
                return window_name

        return "non_trading"

    @staticmethod
    def get_status() -> dict:
        """返回数据源状态摘要"""
        inst = DataSourceManager._instance
        return {
            "adapters": [a.NAME for a in (inst._adapters or [])],
            "trading_time": DataSourceManager.is_trading_time(),
            "time_window": DataSourceManager.get_current_time_window(),
        }


