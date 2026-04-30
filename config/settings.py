# ============================================================
# AutoTrader v3.0 — 全局配置
# 专业级A股T+0量化做T系统
# ============================================================

from pathlib import Path

# ---- 持仓配置（支持多股票，按代码索引）----
POSITIONS = {
    "002539": {
        "name": "云图控股",
        "base_shares": 15300,       # 底仓，不做T时不动
        "base_cost": 10.731,        # 底仓成本价
        "t_shares": 2400,           # 最大做T仓位（单次）
        "t_shares_held": 2400,      # 当前持有做T仓位（运行时动态更新）
    },
    # 可在此添加更多持仓标的：
    # "000858": {
    #     "name": "五粮液",
    #     "base_shares": 5000,
    #     "base_cost": 150.00,
    #     "t_shares": 1000,
    #     "t_shares_held": 1000,
    # },
}

# ---- 自选股池文件路径 ----
STOCK_POOL_FILE = "/Users/dl/.qclaw/workspace/StockSel/data/my_stock_pool.txt"

# ---- 交易时间配置 ----
TRADE_START = "09:30"
TRADE_END = "14:57"               # 14:57停止，留3分钟缓冲
LUNCH_START = "11:30"
LUNCH_END = "13:00"

# 日内时间窗口定义（用于策略权重调整）
TIME_WINDOWS = {
    "open":   ("09:30", "10:00"),  # 开盘窗口：波动剧烈
    "morning": ("10:00", "11:30"), # 上午盘：正常
    "afternoon": ("13:00", "14:30"),# 主力窗口
    "close":  ("14:30", "14:57"),  # 尾盘窗口
}

# ---- 主循环间隔（秒）----
LOOP_INTERVAL = 30                # 每30秒检查一次信号

# ---- 数据源配置 ----
DATA_SOURCE_PRIORITY = ["akshare", "sina", "tencent"]
DATA_RATE_LIMIT = 60              # 每60秒最多请求次数

# ---- 执行层配置 ----
EXECUTION = {
    # 模式: mock=模拟 / signal=仅输出信号(默认) / live=实盘自动交易
    "mode": "signal",

    # ths_trades WEB API（需Win虚拟机部署，默认关闭）
    "ths_web_host": "127.0.0.1",
    "ths_web_port": 6003,

    # 文件信号输出路径（默认开启）
    "signal_dir": "/Volumes/pclouds/Shared/trading_signals",

    # 同花顺客户端路径（备用）
    "ths_exe_path": r"C:\同花顺软件\同花顺\xiadan.exe",
}

# ---- HTTP监控面板 ----
HTTP_PORT = 8080
HTTP_BIND = "127.0.0.1"         # 绑定地址（安全考虑只监听本地）

# ---- 日志配置 ----
LOG_DIR = Path("/Users/dl/WorkBuddy/20260425075457/auto_trader_v3/logs")
LOG_LEVEL = "INFO"
LOG_MAX_SIZE_MB = 50             # 单个日志文件最大50MB
LOG_BACKUP_COUNT = 5             # 保留5个备份日志
