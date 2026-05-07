# ============================================================
# AutoTrader v3.0 — 全局配置 (修复版)
# 自动从 stock_pool.json 加载全部监控股票
# ============================================================

import os
import sys
import json
from pathlib import Path

# ---- 股票池配置（自动从 stock_pool.json 加载）----
# 默认做T仓位配置（用于未单独配置的股票）
DEFAULT_T_SHARES = 1000          # 默认T仓上限（1000股）
DEFAULT_BASE_SHARES = 0          # 无底仓，纯做T
DEFAULT_BASE_COST = 0.0

# 加载 stock_pool.json（支持相对路径和绝对路径）
_POOL_FILE = Path(__file__).parent.parent / "stock_pool.json"
# 如果相对路径找不到，尝试程序所在目录（PyInstaller打包后__file__会变化）
if not _POOL_FILE.exists():
    # 尝试程序根目录（即 stock_pool.json 和 main.py 同目录）
    _exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
    _POOL_FILE = _exe_dir / "stock_pool.json"

if _POOL_FILE.exists():
    with open(_POOL_FILE, "r", encoding="utf-8") as f:
        _raw_pool = json.load(f)
    POSITIONS = {}
    for item in _raw_pool:
        code = item.get("code", "")
        name = item.get("name", code)
        if code:
            POSITIONS[code] = {
                "name": name,
                "base_shares": DEFAULT_BASE_SHARES,
                "base_cost": DEFAULT_BASE_COST,
                "t_shares": DEFAULT_T_SHARES,
                "t_shares_held": DEFAULT_T_SHARES,
            }
    # 强制覆盖大哥的真实持仓（stock_pool.json 里没有底仓数据）
    _REAL_POSITIONS = {
        "002539": {
            "name": "云图控股",
            "base_shares": 14900,   # 大哥真实持仓
            "base_cost": 10.625,    # 成本价
            "t_shares": 2400,
            "t_shares_held": 2400,
        },
    }
    POSITIONS.update(_REAL_POSITIONS)
    print(f"✅ 从 stock_pool.json 加载了 {len(POSITIONS)} 只股票（含真实持仓）")
else:
    # 回退：只监控云图控股（大哥的持仓）
    POSITIONS = {
        "002539": {
            "name": "云图控股",
            "base_shares": 14900,      # 大哥持仓：14900股
            "base_cost": 10.625,       # 成本价：10.625
            "t_shares": 2400,
            "t_shares_held": 2400,
        },
    }
    print(f"⚠️ 未找到 stock_pool.json，退回到默认配置（{len(POSITIONS)} 只）")

# ---- 信号文件输出目录 ----
_SIGNAL_DIR = Path(__file__).parent.parent / "trading_signals"
if getattr(sys, 'frozen', False):
    _SIGNAL_DIR = Path(sys.executable).parent / "trading_signals"
SIGNAL_DIR = _SIGNAL_DIR

# ---- 交易时间配置 ----
TRADE_START = "09:30"
TRADE_END = "14:57"
LUNCH_START = "11:30"
LUNCH_END = "13:00"

TIME_WINDOWS = {
    "open":     ("09:30", "10:00"),
    "morning":  ("10:00", "11:30"),
    "afternoon":("13:00", "14:30"),
    "close":    ("14:30", "14:57"),
}

# ---- 主循环间隔（秒）----
LOOP_INTERVAL = 60

# ---- 数据源配置 ----
DATA_SOURCE_PRIORITY = ["akshare", "sina", "tencent"]
DATA_RATE_LIMIT = 60

# ---- 执行层配置 ----
EXECUTION = {
    "mode": "signal",
    "ths_web_host": "127.0.0.1",
    "ths_web_port": 6003,
    "signal_dir": str(SIGNAL_DIR),
    "ths_exe_path": r"C:\同花顺软件\同花顺\xiadan.exe",
}

# ---- HTTP监控面板 ----
HTTP_PORT = 8080
HTTP_BIND = "0.0.0.0"

# ---- 日志配置 ----
_log_base = Path.home() / "Documents" / "auto_trader_v3"
LOG_DIR = _log_base
LOG_LEVEL = "INFO"
LOG_MAX_SIZE_MB = 50
LOG_BACKUP_COUNT = 5