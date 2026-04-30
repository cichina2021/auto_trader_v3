"""
技术指标计算库 v3.0
基于K线数据列表（list[dict]），纯numpy实现，无pandas依赖

支持的指标：
  MA, EMA, MACD, KDJ, BOLL, RSI, VOLUME_RATIO (v2继承)
  VWAP, ATR, OBV, WILLIAMS_R, CCI (v3新增)

所有函数的入参 klines: list[dict]，每项包含:
  open, close, high, low, volume
"""
import numpy as np
from typing import List, Optional


# ================================================================
# 内部辅助函数
# ================================================================

def _closes(klines: list) -> np.ndarray:
    return np.array([k["close"] for k in klines], dtype=float)


def _highs(klines: list) -> np.ndarray:
    return np.array([k["high"] for k in klines], dtype=float)


def _lows(klines: list) -> np.ndarray:
    return np.array([k["low"] for k in klines], dtype=float)


def _volumes(klines: list) -> np.ndarray:
    return np.array([k["volume"] for k in klines], dtype=float)


# ================================================================
# 趋势类指标
# ================================================================

def MA(klines: list, period: int) -> Optional[float]:
    """简单移动平均线 Simple Moving Average"""
    closes = _closes(klines)
    if len(closes) < period:
        return None
    return float(np.mean(closes[-period:]))


def EMA(klines: list, period: int) -> Optional[float]:
    """指数移动平均线 Exponential Moving Average"""
    closes = _closes(klines)
    if len(closes) < period:
        return None
    k = 2.0 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = price * k + ema * (1 - k)
    return float(ema)


def MACD(klines: list, fast: int = 12, slow: int = 26,
         signal: int = 9) -> dict:
    """
    MACD指标 (Moving Average Convergence Divergence)

    Returns:
        {macd, signal, histogram, cross}
        cross: 'golden'(金叉) / 'dead'(死叉) / None
    """
    closes = _closes(klines)
    if len(closes) < slow + signal:
        return {"macd": None, "signal": None, "histogram": None, "cross": None}

    k_fast = 2.0 / (fast + 1)
    k_slow = 2.0 / (slow + 1)
    k_sig = 2.0 / (signal + 1)

    ema_fast = closes[0]
    ema_slow = closes[0]
    dif_list = []

    for price in closes:
        ema_fast = price * k_fast + ema_fast * (1 - k_fast)
        ema_slow = price * k_slow + ema_slow * (1 - k_slow)
        dif_list.append(ema_fast - ema_slow)

    dea = dif_list[0]
    dea_list = []
    for dif in dif_list:
        dea = dif * k_sig + dea * (1 - k_sig)
        dea_list.append(dea)

    macd_val = dif_list[-1]
    dea_val = dea_list[-1]
    hist = (macd_val - dea_val) * 2

    # 金叉/死叉判断
    cross = None
    if len(dif_list) >= 2:
        prev_diff = dif_list[-2] - dea_list[-2]
        curr_diff = dif_list[-1] - dea_list[-1]
        if prev_diff < 0 and curr_diff >= 0:
            cross = "golden"
        elif prev_diff > 0 and curr_diff <= 0:
            cross = "dead"

    return {
        "macd": round(macd_val, 4),
        "signal": round(dea_val, 4),
        "histogram": round(hist, 4),
        "cross": cross,
    }


# ================================================================
# 震荡类指标
# ================================================================

def KDJ(klines: list, n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    """
    KDJ随机指标 (Stochastic Oscillator)

    Returns:
        {k, d, j, signal}
        signal: 'overbought'(超买K>80,D>80) / 'oversold'(超卖K<20,D<20) / None
    """
    highs = _highs(klines)
    lows = _lows(klines)
    closes = _closes(klines)

    if len(closes) < n:
        return {"k": None, "d": None, "j": None, "signal": None}

    k_val = 50.0
    d_val = 50.0

    for i in range(n - 1, len(closes)):
        period_high = np.max(highs[max(0, i - n + 1):i + 1])
        period_low = np.min(lows[max(0, i - n + 1):i + 1])
        if period_high == period_low:
            rsv = 50.0
        else:
            rsv = (closes[i] - period_low) / (period_high - period_low) * 100
        k_val = (2.0 / 3.0) * k_val + (1.0 / 3.0) * rsv
        d_val = (2.0 / 3.0) * d_val + (1.0 / 3.0) * k_val

    j_val = 3 * k_val - 2 * d_val

    signal = None
    if k_val > 80 and d_val > 80:
        signal = "overbought"
    elif k_val < 20 and d_val < 20:
        signal = "oversold"

    return {
        "k": round(k_val, 2), "d": round(d_val, 2),
        "j": round(j_val, 2), "signal": signal,
    }


def BOLL(klines: list, period: int = 20, std_dev: float = 2.0) -> dict:
    """
    布林带 Bollinger Bands

    Returns:
        {upper, mid, lower, position}
        position: 'above_upper' / 'below_lower' / 'mid_upper' / 'mid_lower'
    """
    closes = _closes(klines)
    if len(closes) < period:
        return {"upper": None, "mid": None, "lower": None, "position": None}

    recent = closes[-period:]
    mid = float(np.mean(recent))
    std = float(np.std(recent, ddof=1))
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    price = closes[-1]

    if price > upper:
        position = "above_upper"
    elif price < lower:
        position = "below_lower"
    elif price > mid:
        position = "mid_upper"
    else:
        position = "mid_lower"

    return {
        "upper": round(upper, 3), "mid": round(mid, 3),
        "lower": round(lower, 3), "position": position,
    }


def RSI(klines: list, period: int = 14) -> Optional[float]:
    """相对强弱指数 Relative Strength Index (0~100)"""
    closes = _closes(klines)
    if len(closes) < period + 1:
        return None

    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def WILLIAMS_R(klines: list, period: int = 14) -> Optional[float]:
    """
    威廉指标 Williams %R (-100 ~ 0)
    > -20: 超买; < -80: 超卖
    """
    highs = _highs(klines)
    lows = _lows(klines)
    closes = _closes(klines)

    if len(closes) < period:
        return None

    i = len(closes) - 1
    hh = float(np.max(highs[max(0, i - period + 1):i + 1]))
    ll = float(np.min(lows[max(0, i - period + 1):i + 1]))

    if hh == ll:
        return -50.0

    wr = (hh - closes[-1]) / (hh - ll) * (-100)
    return round(wr, 2)


def CCI(klines: list, period: int = 20) -> Optional[float]:
    """
    顺势指标 Commodity Channel Index
    > 100: 超买; < -100: 超卖
    """
    closes = _closes(klines)
    highs = _highs(klines)
    lows = _lows(klines)

    if len(closes) < period:
        return None

    recent_closes = closes[-period:]
    recent_highs = highs[-period:]
    recent_lows = lows[-period:]

    # 典型价格 TP = (H+L+C)/3
    tp = (recent_highs + recent_lows + recent_closes) / 3.0
    ma_tp = np.mean(tp)

    mean_deviation = np.mean(np.abs(tp - ma_tp))

    if mean_deviation == 0:
        return 0.0

    cci = (tp[-1] - ma_tp) / (0.015 * mean_deviation)
    return round(float(cci), 2)


# ================================================================
# 量能类指标
# ================================================================

def VOLUME_RATIO(klines: list, period: int = 5) -> Optional[float]:
    """量比 VR = 当日成交量 / 过去N日平均成交量"""
    volumes = _volumes(klines)
    if len(volumes) < period + 1:
        return None
    avg = float(np.mean(volumes[-(period + 1):-1]))
    if avg == 0:
        return None
    return round(volumes[-1] / avg, 2)


def OBV(klines: list) -> Optional[float]:
    """能量潮 On-Balance Volume"""
    closes = _closes(klines)
    volumes = _volumes(klines)

    if len(closes) < 2:
        return None

    obv = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += volumes[i]
        elif closes[i] < closes[i - 1]:
            obv -= volumes[i]

    return round(obv, 0)


def VWAP(klines: list) -> Optional[float]:
    """
    成交量加权平均价 Volume Weighted Average Price
    用于判断当前价格相对于日内均价的位置
    """
    closes = _closes(klines)
    volumes = _volumes(klines)

    if len(closes) == 0 or len(volumes) == 0:
        return None

    total_volume = float(np.sum(volumes))
    if total_volume == 0:
        return None

    vwap = float(np.sum(closes * volumes)) / total_volume
    return round(vwap, 4)


# ================================================================
# 波动率指标
# ================================================================

def ATR(klines: list, period: int = 14) -> Optional[float]:
    """
    平均真实波幅 Average True Range
    用于动态止损止盈和仓位管理
    """
    closes = _closes(klines)
    highs = _highs(klines)
    lows = _lows(klines)

    if len(closes) < period + 1:
        return None

    # TR = max(H-L, |H-PrevC|, |L-PrevC|)
    tr_values = []
    for i in range(1, len(closes)):
        h_l = highs[i] - lows[i]
        h_pc = abs(highs[i] - closes[i - 1])
        l_pc = abs(lows[i] - closes[i - 1])
        tr = max(h_l, h_pc, l_pc)
        tr_values.append(tr)

    if len(tr_values) < period:
        return None

    # ATR = SMA(TR, period)
    atr = float(np.mean(tr_values[-period:]))
    return round(atr, 4)


# ================================================================
# 批量计算接口
# ================================================================

def calculate_all_indicators(klines: list) -> dict:
    """
    一次性计算所有常用指标（用于策略引擎快速获取完整指标集）

    Returns:
        包含所有指标的字典
    """
    result = {}

    # 趋势
    result["MA5"] = MA(klines, 5)
    result["MA10"] = MA(klines, 10)
    result["MA20"] = MA(klines, 20)
    result["EMA12"] = EMA(klines, 12)
    result["EMA26"] = EMA(klines, 26)
    result["MACD"] = MACD(klines)

    # 震荡
    result["KDJ"] = KDJ(klines)
    result["BOLL"] = BOLL(klines)
    result["RSI"] = RSI(klines)
    result["WILLIAMS_R"] = WILLIAMS_R(klines)
    result["CCI"] = CCI(klines)

    # 量能
    result["VOLUME_RATIO"] = VOLUME_RATIO(klines)
    result["OBV"] = OBV(klines)
    result["VWAP"] = VWAP(klines)

    # 波动率
    result["ATR"] = ATR(klines)

    return result
