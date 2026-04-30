"""
AkShare数据适配器
通过akshare库获取A股行情（主数据源）
"""
import logging
from typing import List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class AkShareAdapter:
    """AkShare行情数据适配器（主数据源）"""

    NAME = "akshare"

    def __init__(self):
        self._available = self._check_available()
        if not self._available:
            logger.warning("AkShare未安装或导入失败，将使用备用数据源")

    @staticmethod
    def _check_available() -> bool:
        try:
            import akshare
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        return self._available

    def get_realtime(self, codes: List[str]) -> List[dict]:
        """
        批量获取实时行情

        Args:
            codes: 股票代码列表，如 ["002539", "600519"]

        Returns:
            行情字典列表，每项包含 code, name, price, open, high, low,
            volume, amount, change_pct, prev_close
        """
        if not self._available:
            return []

        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()

            if df is None or len(df) == 0:
                return []

            # 标准化列名映射
            col_map = {
                "代码": "code", "名称": "name",
                "最新价": "price", "今开": "open",
                "最高": "high", "最低": "low",
                "成交量": "volume", "成交额": "amount",
                "涨跌幅": "change_pct", "昨收": "prev_close"
            }
            df = df.rename(columns=col_map)

            # 过滤目标代码
            code_set = {c.strip().upper() for c in codes}
            result = []
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                if code in code_set or code.replace("0", "") in [c.strip() for c in codes]:
                    try:
                        quote = {
                            "code": code,
                            "name": str(row.get("name", "")),
                            "price": float(row.get("price", 0) or 0),
                            "open": float(row.get("open", 0) or 0),
                            "high": float(row.get("high", 0) or 0),
                            "low": float(row.get("low", 0) or 0),
                            "volume": float(row.get("volume", 0) or 0),
                            "amount": float(row.get("amount", 0) or 0),
                            "change_pct": float(row.get("change_pct", 0) or 0),
                            "prev_close": float(row.get("prev_close", 0) or 0),
                        }
                        result.append(quote)
                    except (ValueError, TypeError):
                        continue

            logger.debug(f"AkShare获取{len(codes)}只股票，命中{len(result)}条")
            return result

        except Exception as e:
            logger.error(f"AkShare获取实时行情失败: {e}")
            return []

    def get_kline(self, code: str, period: str = "daily",
                  count: int = 120) -> Optional[pd.DataFrame]:
        """
        获取K线历史数据

        Args:
            code: 股票代码，如 "002539"
            period: 周期 ("daily" / "60m" / "15m" / "5m")
            count: 获取条数

        Returns:
            DataFrame: columns=[date, open, close, high, low, volume]
        """
        if not self._available:
            return None

        # 周期映射到akshare参数
        period_map = {
            "daily": "daily",
            "60m":   "60",
            "15m":   "15",
            "5m":    "5",
        }
        ak_period = period_map.get(period)
        if ak_period is None:
            logger.warning(f"不支持的周期: {period}")
            return None

        try:
            import akshare as ak

            if ak_period == "daily":
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    adjust="qfq"
                )
            else:
                df = ak.stock_zh_a_hist_min_em(
                    symbol=code,
                    period=ak_period,
                    adjust="qfq"
                )

            if df is None or len(df) == 0:
                return None

            # 标准化列名
            col_map = {
                "日期": "date", "开盘": "open",
                "收盘": "close", "最高": "high",
                "最低": "low", "成交量": "volume",
                "成交额": "amount"
            }
            df = df.rename(columns=col_map)

            # 确保必要列存在
            required = {"date", "open", "close", "high", "low", "volume"}
            if not required.issubset(set(df.columns)):
                logger.warning(f"AkShare K线缺少列: {required - set(df.columns)}")
                return None

            # 返回最近N条
            result = df.tail(count).reset_index(drop=True)
            logger.debug(f"AkShare K线[{code}/{period}]获取{len(result)}条")
            return result[["date", "open", "close", "high", "low", "volume"]]

        except Exception as e:
            logger.error(f"AkShare获取K线失败 [{code}/{period}]: {e}")
            return None
