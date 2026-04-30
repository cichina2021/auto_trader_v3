"""
历史数据加载器

用于回测引擎加载历史K线数据。
支持日线和分钟线数据加载。
"""
import logging
from typing import Optional
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """历史K线数据加载器。"""

    @staticmethod
    def load_daily(code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        加载日线历史数据。

        Args:
            code: 股票代码（如 "002539"）
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"

        Returns:
            DataFrame with columns: [date, open, close, high, low, volume, amount]
            或空DataFrame如果加载失败
        """
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq"  # 前复权
            )

            if df is None or len(df) == 0:
                logger.warning(f"无日线数据: {code} {start_date} ~ {end_date}")
                return pd.DataFrame()

            # 标准化列名
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
            })

            # 只保留需要的列
            available_cols = [c for c in ["date", "open", "close", "high", "low", "volume", "amount"]
                             if c in df.columns]
            df = df[available_cols].copy()

            # 日期处理
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            # 数值类型确保
            for col in ["open", "close", "high", "low", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            logger.info(f"加载日线数据: {code} {len(df)}条 "
                       f"({start_date} ~ {end_date})")
            return df

        except ImportError:
            logger.error("akshare 未安装，无法加载历史数据。请运行: pip install akshare")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"加载日线数据失败 {code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def load_minute(code: str, period: str = "60") -> pd.DataFrame:
        """
        加载分钟线历史数据（有限历史）。

        Args:
            code: 股票代码
            period: 周期 "1"/"5"/"15"/"30"/"60"

        Returns:
            DataFrame
        """
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period=period,
                adjust="qfq"
            )

            if df is None or len(df) == 0:
                logger.warning(f"无分钟线数据: {code} period={period}")
                return pd.DataFrame()

            df = df.rename(columns={
                "时间": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
            })

            available_cols = [c for c in ["date", "open", "close", "high", "low", "volume", "amount"]
                             if c in df.columns]
            df = df[available_cols].copy()

            for col in ["open", "close", "high", "low", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            logger.info(f"加载分钟线数据: {code} {len(df)}条 period={period}m")
            return df

        except ImportError:
            logger.error("akshare 未安装")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"加载分钟线数据失败 {code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def dataframe_to_klines(df: pd.DataFrame) -> list:
        """
        将DataFrame转换为策略引擎需要的K线列表格式。

        Args:
            df: 包含 open/close/high/low/volume 列的DataFrame

        Returns:
            [{"open": float, "close": float, "high": float, "low": float, "volume": float}, ...]
        """
        if df is None or len(df) == 0:
            return []

        klines = []
        for _, row in df.iterrows():
            klines.append({
                "open": float(row.get("open", 0)),
                "close": float(row.get("close", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "volume": float(row.get("volume", 0)),
            })
        return klines

    @staticmethod
    def split_train_test(equity_curve_df: pd.DataFrame,
                         train_ratio: float = 0.6,
                         val_ratio: float = 0.2) -> tuple:
        """
        按时间顺序划分训练/验证/测试集（严格按时间，无前视偏差）。

        Args:
            equity_curve_df: 带有date列的DataFrame
            train_ratio: 训练集比例
            val_ratio: 验证集比例

        Returns:
            (train_df, val_df, test_df)
        """
        total = len(equity_curve_df)
        train_end = int(total * train_ratio)
        val_end = int(total * (train_ratio + val_ratio))

        train = equity_curve_df.iloc[:train_end]
        val = equity_curve_df.iloc[train_end:val_end]
        test = equity_curve_df.iloc[val_end:]

        logger.info(f"数据划分: 训练={len(train)}, 验证={len(val)}, "
                   f"测试={len(test)}")
        return train, val, test
