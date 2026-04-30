# ============================================================
# AutoTrader v3.0 — 风控参数配置
# ============================================================

# ---- Kelly公式参数 ----
KELLY_FRACTION = 0.25           # 分数Kelly系数（0.25x = 保守策略）
KELLY_CAP = 0.30                # Kelly仓位上限（不超过资金30%）
KELLY_MIN_TRADES = 10           # 计算Kelly所需的最少历史交易笔数
KELLY_DEFAULT_FRACTION = 0.05   # 无足够历史数据时的默认仓位比例

# ---- VaR风险价值参数 ----
VAR_CONFIDENCE = 0.95           # 置信度95%
VAR_LIMIT = 0.03                # 日VaR上限：权益的3%（超限则停止交易）
VAR_WARNING = 0.015             # VaR警告阈值：权益的1.5%
VAR_MIN_SAMPLES = 100           # 计算VaR所需最少样本数

# ---- 日亏损限额 ----
DAILY_LOSS_HARD_STOP = 0.03     # 单日硬停线：亏损达总资金的3%
DAILY_LOSS_WARNING = 0.015      # 警告线：亏损达1.5%
DAILY_LOSS_ABS_CAP = 8000       # 单日最大绝对亏损金额（元）

# ---- 仓位限制 ----
MAX_POSITION_SINGLE = 0.30      # 单股最大持仓占比（30%）
MAX_POSITION_TOTAL = 0.70       # 总仓位上限（70%）
T_POSITION_MAX_RATIO = 0.20     # 做T仓位占底仓的最大比例

# ---- 交易频率限制 ----
MAX_TRADES_PER_STOCK = 4        # 单只股票日内最大做T轮次
MAX_TRADES_DAILY = 10           # 全局每日最大交易次数
MIN_TRADE_INTERVAL_SEC = 60     # 同一股票最小交易间隔（秒）

# ---- 止损止盈（ATR动态）----
ATR_STOP_LOSS_MULTIPLIER = 2.0  # ATR止损倍数
ATR_TAKE_PROFIT_MULTIPLIER = 3.0 # ATR止盈倍数
FIXED_STOP_LOSS_PCT = 2.5       # 固定止损百分比（ATR不可用时的后备方案）
FIXED_TAKE_PROFIT_PCT = 3.0     # 固定止盈百分比（后备方案）

# ---- 资金配置 ----
INITIAL_CAPITAL = 100000         # 初始资金（元）
RESERVE_RATIO = 0.15            # 预留现金比例（15%保持流动性）

# ---- 连续亏损熔断 ----
CONSECUTIVE_LOSS_LIMIT = 3       # 连续亏损N次触发暂停
CIRCUIT_BREAKER_MINUTES = 30     # 熔断后暂停分钟数
