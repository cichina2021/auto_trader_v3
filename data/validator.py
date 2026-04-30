"""
数据校验层 — 行情数据完整性检查与清洗
"""
import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

# 合理的价格范围（用于异常值检测）
PRICE_MIN = 0.01               # 最低价格（分）
PRICE_MAX = 10000.0            # 最高价格（万元）
CHANGE_PCT_MIN = -11.0         # 最小涨跌幅（跌停-10%含ST）
CHANGE_PCT_MAX = 11.0          # 最大涨跌幅（涨停+10%含ST）
VOLUME_MIN = 0                 # 最小成交量


def validate_quote(quote: dict) -> tuple[bool, str]:
    """
    校验单条实时行情数据

    Args:
        quote: 行情字典，应包含 code, name, price, open, high, low, volume, change_pct

    Returns:
        (是否有效, 错误原因)
    """
    required_fields = {"code", "price", "open", "high", "low", "volume"}
    missing = required_fields - set(quote.keys())
    if missing:
        return False, f"缺少字段: {missing}"

    # 价格有效性
    for field in ("price", "open", "high", "low"):
        val = quote.get(field, 0)
        if val is None or not isinstance(val, (int, float)):
            return False, f"{field}非数值: {val}"
        if val < PRICE_MIN or val > PRICE_MAX:
            return False, f"{field}价格异常({val})"

    # 高低价逻辑：high >= low >= 0
    if quote["high"] < quote["low"]:
        return False, f"高价({quote['high']})<低价({quote['low']})"
    if quote["price"] > quote["high"] or quote["price"] < quote["low"]:
        return False, f"现价超出高低范围"

    # 涨跌幅合理性
    change_pct = quote.get("change_pct")
    if change_pct is not None and isinstance(change_pct, (int, float)):
        if change_pct < CHANGE_PCT_MIN or change_pct > CHANGE_PCT_MAX:
            return False, f"涨跌幅异常({change_pct}%)"

    # 成交量非负
    vol = quote.get("volume", 0)
    if vol is not None and vol < VOLUME_MIN:
        return False, f"成交量为负"

    return True, ""


def validate_kline(df) -> tuple[bool, str]:
    """
    校验K线DataFrame

    Args:
        df: pandas DataFrame，需包含 date, open, close, high, low, volume

    Returns:
        (是否有效, 错误原因)
    """
    import pandas as pd
    if df is None or len(df) == 0:
        return False, "空DataFrame"

    required_cols = {"date", "open", "close", "high", "low", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        return False, f"K线缺列: {missing}"

    # NaN检测
    nan_counts = df[required_cols].isnull().sum()
    total_nans = nan_counts.sum()
    if total_nans > 0:
        cols_with_nan = nan_counts[nan_counts > 0].to_dict()
        logger.warning(f"K线存在NaN值: {cols_with_nan}")

    # 高低逻辑
    invalid_hl = (df["high"] < df["low"]).sum()
    if invalid_hl > 0:
        return False, f"{invalid_hl}行高<低"

    # 价格范围
    for col in ["open", "close", "high", "low"]:
        out_of_range = ((df[col] < PRICE_MIN) | (df[col] > PRICE_MAX)).sum()
        if out_of_range > 0:
            return False, f"{col}有{out_of_range}个异常值"

    return True, ""


def sanitize_kline(df):
    """
    清洗K线数据：前向填充NaN、截断异常值、排序

    Returns:
        清洗后的DataFrame副本
    """
    import pandas as pd
    cleaned = df.copy()

    # 排序（按日期升序）
    if "date" in cleaned.columns:
        cleaned = cleaned.sort_values("date").reset_index(drop=True)

    # 前向填充数值列的NaN
    num_cols = ["open", "close", "high", "low", "volume"]
    for col in num_cols:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].ffill().bfill()

    # 截断极端价格到合理范围
    for col in ["open", "close", "high", "low"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].clip(lower=PRICE_MIN, upper=PRICE_MAX)

    # 确保high>=low
    mask = cleaned["high"] < cleaned["low"]
    if mask.any():
        avg = (cleaned.loc[mask, "high"] + cleaned.loc[mask, "low"]) / 2
        cleaned.loc[mask, "high"] = avg
        cleaned.loc[mask, "low"] = avg
        logger.warning(f"修正{mask.sum()}条高低价倒置")

    return cleaned


def validate_order_flow(data: dict) -> tuple[bool, str]:
    """
    校验订单流数据

    Returns:
        (是否有效, 错误原因)
    """
    if data is None or not isinstance(data, dict):
        return False, "订单流数据为空或格式错误"
    if "buy_volume" not in data or "sell_volume" not in data:
        return False, "缺少买/卖量字段"
    return True, ""
