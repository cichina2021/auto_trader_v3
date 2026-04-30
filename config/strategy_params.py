# ============================================================
# AutoTrader v3.0 — 策略参数配置
# ============================================================

# ---- 多因子模型权重（总和=1.0）----
FACTOR_WEIGHTS = {
    "momentum":        0.30,  # 动量因子
    "volatility":      0.25,  # 波动率因子
    "volume":          0.20,  # 量能因子
    "microstructure":  0.25,  # 微观结构因子
}

# ---- 贝叶斯融合参数 ----
BAYESIAN_PRIOR = 0.5            # 先验概率（默认50%盈利概率）
BAYESIAN_MIN_CONFIDENCE = 0.60  # 贝叶斯后验最低置信度

# ---- 多周期MACD共振权重 ----
MULTI_TF_WEIGHTS = {
    "daily":  0.40,   # 日线权重40%
    "60m":    0.30,   # 60分钟线权重30%
    "15m":    0.20,   # 15分钟线权重20%
    "5m":     0.10,   # 5分钟线权重10%
}

# ---- 日内时间窗口风险系数 ----
TIME_WINDOW_RISK_FACTOR = {
    "open":      0.6,   # 开盘窗口：降低信号强度，只接受高置信信号
    "morning":   1.0,   # 上午盘：正常
    "afternoon": 1.0,   # 下午盘：正常
    "close":     0.4,   # 尾盘窗口：只做平仓不做开仓
}

# ---- 信号生成阈值 ----
MIN_CONFIDENCE = 0.65           # 综合信号最低置信度
MIN_FACTORS_AGREE = 2           # 至少N个因子方向一致才触发信号

# ---- 做T参数 ----
T_CONFIG = {
    "buy_drop_threshold":     -0.8,   # 买入触发：跌幅超此阈值
    "sell_rise_threshold":    0.8,    # 卖出触发：涨幅超此阈值
    "macd_hist_threshold":    0.02,   # MACD柱状图阈值
    "volume_ratio_min":       1.5,    # 最小量比
}
