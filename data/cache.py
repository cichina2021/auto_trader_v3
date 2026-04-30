"""
数据缓存层 — 基于TTL的线程安全缓存
避免频繁请求外部数据源，减少被限流风险
"""
import time
import threading
import logging
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class DataCache:
    """TTL-based thread-safe data cache"""

    def __init__(self):
        self._store: dict = {}
        self._timestamps: dict = {}
        self._lock = threading.RLock()

    def get(self, key: str, ttl_seconds: int,
            fetch_func: Optional[Callable] = None) -> Optional[Any]:
        """
        获取缓存数据，过期则自动重新获取

        Args:
            key: 缓存键（通常为 code + data_type，如 "002539_realtime"）
            ttl_seconds: 有效时间（秒）
            fetch_func: 过期时的回调函数，用于重新获取数据。若为None则返回None

        Returns:
            缓存的数据，或fetch_func的新结果，或None
        """
        with self._lock:
            now = time.time()

            # 命中且未过期
            if (key in self._store and key in self._timestamps):
                age = now - self._timestamps[key]
                if age < ttl_seconds:
                    return self._store[key]

            # 未命中或已过期 → 调用fetch_func刷新
            if fetch_func is not None:
                try:
                    data = fetch_func()
                    if data is not None:
                        self._store[key] = data
                        self._timestamps[key] = now
                        return data
                except Exception as e:
                    logger.warning(f"缓存刷新失败 [{key}]: {e}")

                # 刷新失败但旧数据存在 → 降级返回旧数据（宽限期=2×TTL）
                if key in self._store:
                    old_age = now - self._timestamps[key]
                    if old_age < ttl_seconds * 2:
                        logger.debug(f"使用过期缓存 [{key}] (超时{old_age:.1f}s)")
                        return self._store[key]

            # 彻底无数据
            return None

    def put(self, key: str, data: Any) -> None:
        """手动写入缓存"""
        with self._lock:
            self._store[key] = data
            self._timestamps[key] = time.time()

    def invalidate(self, key: str) -> None:
        """使指定key的缓存失效"""
        with self._lock:
            self._store.pop(key, None)
            self._timestamps.pop(key, None)

    def invalidate_pattern(self, prefix: str) -> None:
        """批量使匹配前缀的缓存失效（如某只股票的所有缓存）"""
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]
                self._timestamps.pop(k, None)
            logger.debug(f"批量失效前缀[{prefix}]：移除{len(keys_to_remove)}条")

    def cleanup(self) -> int:
        """清理所有过期条目，返回清理数量"""
        now = time.time()
        count = 0
        with self._lock:
            keys_to_remove = []
            for key in list(self._store.keys()):
                if key in self._timestamps:
                    # 无TTL标记的条目保留（由put直接写入）
                    continue
            # cleanup不删除任何东西——需要知道每个key的TTL才能判断
            # 实际使用中通过定期调用invalidate_pattern来管理
        return count

    def stats(self) -> dict:
        """返回缓存统计信息"""
        with self._lock:
            return {
                "total_keys": len(self._store),
                "keys": list(self._store.keys()),
            }


# ---- 全局缓存实例 ----
_cache_instance = None
_cache_lock = threading.Lock()


def get_cache() -> DataCache:
    """获取全局单例缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = DataCache()
    return _cache_instance


# ---- TTL常量 ----
CACHE_TTL_REALTIME = 8     # 实时行情缓存8秒
CACHE_TTL_KLINE = 60       # K线数据缓存60秒
CACHE_TTL_ORDER_FLOW = 30  # 订单流数据缓存30秒
