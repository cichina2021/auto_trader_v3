"""
专业Web监控面板 v2.0

Bloomberg/同花顺风格专业金融终端，双主题（暗色+亮色），局部动态刷新。
纯原生 HTML+CSS+JS，零外部依赖，兼容 PyInstaller 打包。

A股配色规则：红涨绿跌
"""
import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DashboardHandler(BaseHTTPRequestHandler):
    """
    Web监控面板HTTP处理器 v2.0。

    get_state 为类级别回调，由TradingSystem在启动时注入。
    """

    def __init__(self, *args, **kwargs):
        self.get_state = getattr(self.__class__, 'get_state', lambda: {})
        super().__init__(*args)

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {format % args}")

    # ==================== HTTP 路由 ====================

    def do_GET(self):
        path = urlparse(self.path).path
        routes = {
            "/": self._handle_dashboard,
            "/index.html": self._handle_dashboard,
            "/api/status": self._handle_api_status,
            "/api/positions": self._handle_api_positions,
            "/api/signals": self._handle_api_signals,
            "/api/risk": self._handle_api_risk,
            "/api/trades": self._handle_api_trades,
            "/api/alerts": self._handle_api_alerts,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self._send_response(404, "text/plain", "Not Found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/scan":
            self._send_response(200, "application/json",
                               json.dumps({"status": "scan_triggered"}))
        else:
            self._send_response(404, "text/plain", "Not Found")

    # ==================== API 处理 ====================

    def _handle_dashboard(self):
        state = self.get_state()
        html = self._build_html(state)
        self._send_response(200, "text/html; charset=utf-8", html)

    def _handle_api_status(self):
        state = self.get_state()
        self._send_response(200, "application/json", json.dumps(state, ensure_ascii=False))

    def _handle_api_positions(self):
        state = self.get_state()
        self._send_response(200, "application/json",
                           json.dumps(state.get("positions", []), ensure_ascii=False))

    def _handle_api_signals(self):
        state = self.get_state()
        self._send_response(200, "application/json",
                           json.dumps(state.get("signals", []), ensure_ascii=False))

    def _handle_api_risk(self):
        state = self.get_state()
        self._send_response(200, "application/json",
                           json.dumps(state.get("risk", {}), ensure_ascii=False))

    def _handle_api_trades(self):
        state = self.get_state()
        self._send_response(200, "application/json",
                           json.dumps(state.get("trades", []), ensure_ascii=False))

    def _handle_api_alerts(self):
        state = self.get_state()
        self._send_response(200, "application/json",
                           json.dumps(state.get("alerts", []), ensure_ascii=False))

    def _send_response(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    # ==================== CSS 主题系统 ====================

    def _get_theme_css(self) -> str:
        return """
/* === 暗色主题 (默认) - Bloomberg/同花顺专业风 === */
:root, [data-theme="dark"] {
    --bg-primary: #080c14;
    --bg-secondary: #0f1923;
    --bg-card: #141e2b;
    --bg-card-inner: #0b1220;
    --bg-hover: #1a2836;
    --bg-input: #0d1520;
    --border-color: #1e2d3d;
    --border-subtle: #162231;
    --text-primary: #e8edf3;
    --text-secondary: #8899aa;
    --text-muted: #4a5f75;
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --accent-teal: #14b8a6;
    --accent-purple: #8b5cf6;
    --price-up: #ef4444;
    --price-down: #22c55e;
    --price-flat: #94a3b8;
    --neon-blue: rgba(59,130,246,0.15);
    --neon-red: rgba(239,68,68,0.4);
    --neon-green: rgba(34,197,94,0.4);
    --glow-up: 0 0 12px rgba(239,68,68,0.3);
    --glow-down: 0 0 12px rgba(34,197,94,0.3);
    --glow-card: 0 0 20px rgba(59,130,246,0.08);
    --shadow-sm: 0 2px 8px rgba(0,0,0,0.4);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.5);
    --shadow-lg: 0 8px 32px rgba(0,0,0,0.6);
    --header-bg: linear-gradient(135deg, #0c1622 0%, #111d2e 50%, #0f1923 100%);
    --scrollbar-track: #0f1923;
    --scrollbar-thumb: #2a3f55;
}

/* === 亮色主题 - 商务风 === */
[data-theme="light"] {
    --bg-primary: #f0f4f8;
    --bg-secondary: #ffffff;
    --bg-card: #ffffff;
    --bg-card-inner: #f8fafc;
    --bg-hover: #eef2f7;
    --bg-input: #f1f5f9;
    --border-color: #e2e8f0;
    --border-subtle: #f1f5f9;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
    --accent-blue: #2563eb;
    --accent-cyan: #0891b2;
    --accent-teal: #0d9488;
    --accent-purple: #7c3aed;
    --price-up: #dc2626;
    --price-down: #16a34a;
    --price-flat: #64748b;
    --neon-blue: rgba(37,99,235,0.08);
    --neon-red: rgba(220,38,38,0.1);
    --neon-green: rgba(22,163,74,0.1);
    --glow-up: none;
    --glow-down: none;
    --glow-card: 0 4px 12px rgba(0,0,0,0.06);
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
    --shadow-md: 0 2px 8px rgba(0,0,0,0.1);
    --shadow-lg: 0 4px 16px rgba(0,0,0,0.12);
    --header-bg: linear-gradient(135deg, #1e40af 0%, #2563eb 50%, #3b82f6 100%);
    --scrollbar-track: #f1f5f9;
    --scrollbar-thumb: #cbd5e1;
}
"""

    # ==================== 布局 CSS ====================

    def _get_layout_css(self) -> str:
        return """
* { margin: 0; padding: 0; box-sizing: border-box; }
html { font-size: 14px; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--scrollbar-track); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-blue); }

/* === Header === */
.header {
    background: var(--header-bg);
    border-bottom: 1px solid var(--border-color);
    padding: 0 28px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: var(--shadow-md);
}
.header-left { display: flex; align-items: center; gap: 16px; }
.logo {
    font-size: 18px; font-weight: 700;
    color: #f0f6fc;
    letter-spacing: 0.5px;
    display: flex; align-items: center; gap: 10px;
}
.logo-icon {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; font-weight: 900; color: #fff;
    box-shadow: 0 2px 8px rgba(59,130,246,0.3);
}
.status-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: 500;
    transition: all 0.3s;
}
.status-badge.running { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
.status-badge.halted { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    animation: dot-pulse 2s ease-in-out infinite;
}
.status-badge.running .status-dot { background: #4ade80; }
.status-badge.halted .status-dot { background: #f87171; animation: none; opacity: 0.7; }
@keyframes dot-pulse { 0%,100% { opacity: 1; box-shadow: 0 0 4px currentColor; } 50% { opacity: 0.3; box-shadow: none; } }

.header-right { display: flex; align-items: center; gap: 20px; }
.header-metrics { display: flex; gap: 28px; }
.metric { text-align: center; }
.metric-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
.metric-value { font-size: 18px; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.metric-value.up { color: var(--price-up); text-shadow: var(--glow-up); }
.metric-value.down { color: var(--price-down); text-shadow: var(--glow-down); }
.metric-value.time { font-size: 13px; color: var(--text-secondary); font-weight: 500; }

.theme-btn {
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
    color: #f0f6fc; border-radius: 8px; width: 36px; height: 36px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-size: 16px; transition: all 0.2s;
}
.theme-btn:hover { background: rgba(255,255,255,0.15); transform: scale(1.05); }
[data-theme="light"] .theme-btn { background: rgba(0,0,0,0.06); border-color: rgba(0,0,0,0.1); color: #475569; }
[data-theme="light"] .theme-btn:hover { background: rgba(0,0,0,0.1); }

/* === 主体布局 === */
.main-container {
    flex: 1; padding: 20px 28px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto auto;
    gap: 20px;
    max-width: 1600px;
    margin: 0 auto;
    width: 100%;
}

/* === Card === */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
    transition: box-shadow 0.3s, border-color 0.3s;
    box-shadow: var(--shadow-sm);
}
.card:hover {
    box-shadow: var(--glow-card);
    border-color: rgba(59,130,246,0.2);
}
.card-header {
    padding: 14px 20px;
    border-bottom: 1px solid var(--border-subtle);
    display: flex; align-items: center; justify-content: space-between;
    background: var(--bg-card-inner);
}
.card-title {
    font-size: 13px; font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex; align-items: center; gap: 8px;
}
.card-title-icon {
    width: 18px; height: 18px; border-radius: 4px;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 11px;
}
.card-title-icon.blue { background: rgba(59,130,246,0.15); color: var(--accent-blue); }
.card-title-icon.green { background: rgba(34,197,94,0.15); color: var(--price-down); }
.card-title-icon.purple { background: rgba(139,92,246,0.15); color: var(--accent-purple); }
.card-title-icon.cyan { background: rgba(6,182,212,0.15); color: var(--accent-cyan); }
.card-title-icon.orange { background: rgba(245,158,11,0.15); color: #f59e0b; }
.card-body { padding: 16px 20px; }
.card.full-width { grid-column: 1 / -1; }
.card-badge {
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    background: var(--bg-hover); color: var(--text-muted);
}

/* === Table === */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th {
    text-align: left; padding: 10px 12px;
    color: var(--text-muted); font-weight: 500;
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.5px; border-bottom: 1px solid var(--border-subtle);
    white-space: nowrap;
}
td { padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); }
tbody tr { transition: background 0.15s; }
tbody tr:hover { background: var(--bg-hover); }
tbody tr:last-child td { border-bottom: none; }
.code { color: var(--accent-blue); font-weight: 600; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }

/* === Footer === */
.footer {
    padding: 16px 28px;
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border-subtle);
    display: flex; align-items: center; justify-content: center; gap: 20px;
}
.footer a { color: var(--accent-blue); text-decoration: none; }
.footer a:hover { text-decoration: underline; }

/* === 空状态 === */
.empty-state {
    color: var(--text-muted); text-align: center;
    padding: 32px 16px; font-size: 13px;
}

/* === 响应式 === */
@media (max-width: 1024px) {
    .main-container { grid-template-columns: 1fr; padding: 16px; }
    .header-metrics { gap: 16px; }
    .metric-value { font-size: 15px; }
}
@media (max-width: 640px) {
    .header { padding: 0 16px; height: 56px; }
    .header-metrics { display: none; }
    .main-container { padding: 12px; gap: 12px; }
}
"""

    # ==================== 组件 CSS ====================

    def _get_component_css(self) -> str:
        return """
/* === 信号卡片 === */
.signal-list { display: flex; flex-direction: column; gap: 8px; }
.signal-card {
    background: var(--bg-card-inner);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 14px 16px;
    transition: all 0.25s;
    border-left: 3px solid var(--accent-blue);
    cursor: default;
}
.signal-card:hover {
    transform: translateX(3px);
    box-shadow: var(--glow-card);
    border-color: rgba(59,130,246,0.25);
}
.signal-card.buy { border-left-color: var(--price-up); }
.signal-card.sell { border-left-color: var(--price-down); }
.signal-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.signal-code { font-weight: 700; font-family: 'SF Mono', monospace; font-size: 14px; color: var(--text-primary); }
.signal-action {
    padding: 2px 10px; border-radius: 4px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.signal-action.buy { background: rgba(239,68,68,0.12); color: var(--price-up); }
.signal-action.sell { background: rgba(34,197,94,0.12); color: var(--price-down); }
.signal-confidence {
    margin-left: auto; font-size: 12px; font-weight: 600;
    color: var(--accent-cyan); font-variant-numeric: tabular-nums;
}
.signal-meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); }
.signal-meta span { display: flex; align-items: center; gap: 4px; }
.signal-reason { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

/* === 风控面板 === */
.risk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.risk-item {
    background: var(--bg-card-inner);
    border: 1px solid var(--border-subtle);
    border-radius: 10px; padding: 14px 16px;
    transition: all 0.2s;
}
.risk-item:hover { border-color: rgba(59,130,246,0.2); }
.risk-item.wide { grid-column: 1 / -1; }
.risk-label { font-size: 11px; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.risk-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.risk-value.safe { color: var(--price-down); }
.risk-value.warn { color: #f59e0b; }
.risk-value.danger { color: var(--price-up); }

/* === 进度条 === */
.progress-wrap { margin-top: 8px; }
.progress-bar {
    height: 6px; background: var(--bg-hover); border-radius: 3px;
    overflow: hidden; position: relative;
}
.progress-fill {
    height: 100%; border-radius: 3px;
    transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94), background 0.3s;
    position: relative;
}
.progress-fill.safe { background: linear-gradient(90deg, #22c55e, #4ade80); }
.progress-fill.warn { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.progress-fill.danger { background: linear-gradient(90deg, #ef4444, #f87171); }
[data-theme="dark"] .progress-fill.safe { box-shadow: 0 0 8px rgba(34,197,94,0.4); }
[data-theme="dark"] .progress-fill.danger { box-shadow: 0 0 8px rgba(239,68,68,0.4); }

/* === 告警 === */
.alert-list { display: flex; flex-direction: column; gap: 6px; }
.alert-item {
    background: var(--bg-card-inner);
    border: 1px solid var(--border-subtle);
    border-radius: 8px; padding: 10px 14px;
    display: flex; align-items: center; gap: 10px;
    font-size: 12px; transition: all 0.2s;
}
.alert-item:hover { background: var(--bg-hover); }
.alert-badge {
    font-size: 10px; font-weight: 700; padding: 2px 8px;
    border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px;
    flex-shrink: 0;
}
.alert-badge.critical { background: rgba(239,68,68,0.12); color: var(--price-up); }
.alert-badge.warning { background: rgba(245,158,11,0.12); color: #f59e0b; }
.alert-badge.info { background: rgba(59,130,246,0.12); color: var(--accent-blue); }
.alert-msg { flex: 1; color: var(--text-secondary); }
.alert-time { color: var(--text-muted); font-size: 11px; flex-shrink: 0; }

/* === 动画 === */
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
.signal-card { animation: fadeIn 0.3s ease-out; }
.alert-item { animation: fadeIn 0.3s ease-out; }
"""

    # ==================== HTML 生成 ====================

    def _get_header_html(self, state: dict) -> str:
        return """
<header class="header">
    <div class="header-left">
        <div class="logo">
            <div class="logo-icon">T</div>
            A股做T量化系统
        </div>
        <div class="status-badge running" id="status-badge">
            <span class="status-dot"></span>
            <span id="status-text">运行中</span>
        </div>
    </div>
    <div class="header-right">
        <div class="header-metrics">
            <div class="metric">
                <div class="metric-label">总资金</div>
                <div class="metric-value" id="metric-capital">--</div>
            </div>
            <div class="metric">
                <div class="metric-label">今日盈亏</div>
                <div class="metric-value" id="metric-pnl">--</div>
            </div>
            <div class="metric">
                <div class="metric-label">更新时间</div>
                <div class="metric-value time" id="metric-time">--</div>
            </div>
        </div>
        <button class="theme-btn" id="theme-toggle" onclick="toggleTheme()" title="切换主题">☀</button>
    </div>
</header>
"""

    def _get_positions_html(self, state: dict) -> str:
        return """
<div class="card" id="positions-card">
    <div class="card-header">
        <div class="card-title">
            <span class="card-title-icon blue">&#9634;</span>
            持仓监控
        </div>
        <span class="card-badge" id="positions-count">0 只</span>
    </div>
    <div class="card-body" style="padding:0;">
        <table>
            <thead><tr>
                <th>代码</th><th>名称</th><th>T仓上限</th>
                <th>T仓持有</th><th>T仓成本</th><th>今日交易</th>
            </tr></thead>
            <tbody id="positions-tbody">
                <tr><td colspan="6" class="empty-state">暂无持仓数据</td></tr>
            </tbody>
        </table>
    </div>
</div>
"""

    def _get_signals_html(self, state: dict) -> str:
        return """
<div class="card" id="signals-card">
    <div class="card-header">
        <div class="card-title">
            <span class="card-title-icon cyan">&#9889;</span>
            交易信号
        </div>
        <span class="card-badge" id="signals-count">0 条</span>
    </div>
    <div class="card-body">
        <div class="signal-list" id="signals-list">
            <div class="empty-state">暂无信号</div>
        </div>
    </div>
</div>
"""

    def _get_risk_html(self, state: dict) -> str:
        return """
<div class="card" id="risk-card">
    <div class="card-header">
        <div class="card-title">
            <span class="card-title-icon purple">&#9881;</span>
            风控指标
        </div>
    </div>
    <div class="card-body">
        <div class="risk-grid">
            <div class="risk-item">
                <div class="risk-label">VaR (95%)</div>
                <div class="risk-value safe" id="risk-var">--</div>
                <div class="progress-wrap">
                    <div class="progress-bar">
                        <div class="progress-fill safe" id="risk-var-fill" style="width:0%"></div>
                    </div>
                </div>
            </div>
            <div class="risk-item">
                <div class="risk-label">Kelly 仓位建议</div>
                <div class="risk-value" id="risk-kelly">--</div>
            </div>
            <div class="risk-item">
                <div class="risk-label">历史胜率</div>
                <div class="risk-value" id="risk-winrate">--</div>
            </div>
            <div class="risk-item">
                <div class="risk-label">今日交易次数</div>
                <div class="risk-value" id="risk-trades">0</div>
            </div>
            <div class="risk-item wide">
                <div class="risk-label">日亏损进度 (硬停 3%)</div>
                <div class="risk-value" id="risk-loss">0.00%</div>
                <div class="progress-wrap">
                    <div class="progress-bar">
                        <div class="progress-fill safe" id="risk-loss-fill" style="width:0%"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

    def _get_trades_html(self, state: dict) -> str:
        return """
<div class="card" id="trades-card">
    <div class="card-header">
        <div class="card-title">
            <span class="card-title-icon green">&#9783;</span>
            交易记录
        </div>
        <span class="card-badge" id="trades-count">0 条</span>
    </div>
    <div class="card-body" style="padding:0;">
        <table>
            <thead><tr>
                <th>时间</th><th>代码</th><th>方向</th>
                <th>价格</th><th>股数</th><th>盈亏</th>
            </tr></thead>
            <tbody id="trades-tbody">
                <tr><td colspan="6" class="empty-state">暂无交易记录</td></tr>
            </tbody>
        </table>
    </div>
</div>
"""

    def _get_alerts_html(self, state: dict) -> str:
        return """
<div class="card full-width" id="alerts-card">
    <div class="card-header">
        <div class="card-title">
            <span class="card-title-icon orange">&#9888;</span>
            系统告警
        </div>
        <span class="card-badge" id="alerts-count">0 条</span>
    </div>
    <div class="card-body">
        <div class="alert-list" id="alerts-list">
            <div class="empty-state">暂无告警</div>
        </div>
    </div>
</div>
"""

    def _get_footer_html(self, state: dict) -> str:
        last_scan = state.get("last_scan", "--")
        scan_count = state.get("scan_count", 0)
        return f"""
<footer class="footer">
    <span>A股做T量化交易系统 v3.0</span>
    <span>|</span>
    <span>最后扫描: <strong id="footer-scan">{last_scan}</strong></span>
    <span>|</span>
    <span>扫描轮次: <strong id="footer-count">{scan_count}</strong></span>
    <span>|</span>
    <a href="/api/status" target="_blank">API</a>
    <span>|</span>
    <span id="footer-refresh" style="color:var(--accent-blue);cursor:pointer;" onclick="fetchAndUpdate()">手动刷新</span>
</footer>
"""

    # ==================== JavaScript ====================

    def _get_javascript(self) -> str:
        return """
// ==================== 主题切换 ====================
function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme') || 'dark';
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('at_theme', next);
    document.getElementById('theme-toggle').textContent = next === 'light' ? '\\u263E' : '\\u2600';
}
function initTheme() {
    var saved = localStorage.getItem('at_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = saved === 'light' ? '\\u263E' : '\\u2600';
}

// ==================== 数据获取 ====================
var API = {
    status: '/api/status',
    positions: '/api/positions',
    signals: '/api/signals',
    risk: '/api/risk',
    trades: '/api/trades',
    alerts: '/api/alerts'
};
var cache = { status: null, positions: null, signals: null, risk: null, trades: null, alerts: null };
var REFRESH_MS = 5000;
var refreshTimer = null;

function fetchJSON(url) {
    return fetch(url).then(function(r) { return r.json(); }).catch(function(e) { console.error('Fetch error:', url, e); return null; });
}

function fetchAllData() {
    var keys = Object.keys(API);
    var promises = keys.map(function(k) { return fetchJSON(API[k]).then(function(d) { return { key: k, data: d }; }); });
    return Promise.all(promises).then(function(results) {
        var data = {};
        results.forEach(function(r) { data[r.key] = r.data; });
        return data;
    });
}

function fetchAndUpdate() {
    fetchAllData().then(function(data) { if (data) updateDOM(data); });
}

// ==================== 工具函数 ====================
function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function fmtNum(n) { return n != null ? n.toLocaleString('zh-CN', {minimumFractionDigits: 0, maximumFractionDigits: 0}) : '--'; }
function fmtPct(n) { return n != null ? (n * 100).toFixed(2) + '%' : '--'; }
function fmtMoney(n) { return n != null ? n.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '--'; }
function pnlClass(v) { return v > 0 ? 'up' : v < 0 ? 'down' : ''; }
function pnlSign(v) { return v >= 0 ? '+' : ''; }

// ==================== DOM 更新 ====================
function updateDOM(data) {
    if (data.status && JSON.stringify(data.status) !== JSON.stringify(cache.status)) { updateHeader(data.status); cache.status = data.status; }
    if (data.positions && JSON.stringify(data.positions) !== JSON.stringify(cache.positions)) { updatePositions(data.positions); cache.positions = data.positions; }
    if (data.signals && JSON.stringify(data.signals) !== JSON.stringify(cache.signals)) { updateSignals(data.signals); cache.signals = data.signals; }
    if (data.risk && JSON.stringify(data.risk) !== JSON.stringify(cache.risk)) { updateRisk(data.risk); cache.risk = data.risk; }
    if (data.trades && JSON.stringify(data.trades) !== JSON.stringify(cache.trades)) { updateTrades(data.trades); cache.trades = data.trades; }
    if (data.alerts && JSON.stringify(data.alerts) !== JSON.stringify(cache.alerts)) { updateAlerts(data.alerts); cache.alerts = data.alerts; }
    updateTime();
}

function updateHeader(s) {
    var badge = document.getElementById('status-badge');
    var stxt = document.getElementById('status-text');
    var isRun = (s.status === 'running');
    badge.className = 'status-badge ' + (isRun ? 'running' : 'halted');
    if (stxt) stxt.textContent = isRun ? '运行中' : '已暂停';

    var capEl = document.getElementById('metric-capital');
    if (capEl) capEl.textContent = fmtNum(s.capital);

    var pnlEl = document.getElementById('metric-pnl');
    var pnl = s.daily_pnl || 0;
    var pnlPct = s.daily_pnl_pct || 0;
    if (pnlEl) {
        pnlEl.textContent = pnlSign(pnl) + fmtMoney(pnl) + ' (' + pnlSign(pnlPct) + fmtPct(pnlPct) + ')';
        pnlEl.className = 'metric-value ' + pnlClass(pnl);
    }

    var el = document.getElementById('footer-scan');
    if (el) el.textContent = s.last_scan || '--';
    var ec = document.getElementById('footer-count');
    if (ec) ec.textContent = s.scan_count || 0;
}

function updatePositions(positions) {
    var tbody = document.getElementById('positions-tbody');
    var countEl = document.getElementById('positions-count');
    if (!tbody) return;

    var html = '';
    var items = positions;
    if (items && typeof items === 'object' && !Array.isArray(items)) {
        items = Object.entries(items).map(function(e) { return Object.assign({code: e[0]}, e[1]); });
    }
    if (!items || items.length === 0) {
        html = '<tr><td colspan="6" class="empty-state">暂无持仓数据</td></tr>';
    } else {
        items.forEach(function(p) {
            html += '<tr><td><span class="code">' + esc(p.code || '') + '</span></td>'
                + '<td>' + esc(p.name || '') + '</td>'
                + '<td>' + (p.t_max || 0) + '</td>'
                + '<td>' + (p.t_held || 0) + '</td>'
                + '<td>' + (p.t_cost ? p.t_cost.toFixed(3) : '0.000') + '</td>'
                + '<td>' + (p.today_trades || 0) + '</td></tr>';
        });
    }
    tbody.innerHTML = html;
    if (countEl) countEl.textContent = items ? items.length : 0 + ' 只';
}

function updateSignals(signals) {
    var list = document.getElementById('signals-list');
    var countEl = document.getElementById('signals-count');
    if (!list) return;
    if (!signals || signals.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无信号</div>';
        if (countEl) countEl.textContent = '0 条';
        return;
    }
    var html = '';
    signals.forEach(function(s) {
        var isBuy = (s.action === 'BUY');
        var cls = isBuy ? 'buy' : 'sell';
        var actCn = isBuy ? '买入' : '卖出';
        html += '<div class="signal-card ' + cls + '">'
            + '<div class="signal-header">'
            + '<span class="signal-code">' + esc(s.code || '') + '</span>'
            + '<span class="signal-action ' + cls + '">' + actCn + '</span>'
            + '<span class="signal-confidence">' + (s.confidence ? (s.confidence * 100).toFixed(0) : 0) + '%</span>'
            + '</div>'
            + '<div class="signal-meta">'
            + '<span>\\u26A1 ' + (s.price ? s.price.toFixed(2) : '--') + '</span>'
            + '<span>\\u25A0 ' + (s.shares || '--') + '股</span>'
            + '</div>'
            + (s.reason ? '<div class="signal-reason">' + esc(s.reason) + '</div>' : '')
            + '</div>';
    });
    list.innerHTML = html;
    if (countEl) countEl.textContent = signals.length + ' 条';
}

function updateRisk(risk) {
    var varEl = document.getElementById('risk-var');
    var varFill = document.getElementById('risk-var-fill');
    var varVal = risk.var || risk.var_pct || 0;
    if (varEl) { varEl.textContent = fmtPct(varVal); }
    if (varFill) {
        var pct = Math.min(varVal * 100, 100);
        var cls = varVal < 0.015 ? 'safe' : varVal < 0.03 ? 'warn' : 'danger';
        varFill.style.width = pct + '%';
        varFill.className = 'progress-fill ' + cls;
    }

    var kellyEl = document.getElementById('risk-kelly');
    if (kellyEl) {
        var kf = risk.kelly_fraction || risk.kelly || 0;
        kellyEl.textContent = fmtPct(kf);
    }

    var wrEl = document.getElementById('risk-winrate');
    if (wrEl) wrEl.textContent = fmtPct(risk.win_rate || 0);

    var trEl = document.getElementById('risk-trades');
    if (trEl) trEl.textContent = risk.total_trades || risk.trades_today || 0;

    var lossEl = document.getElementById('risk-loss');
    var lossFill = document.getElementById('risk-loss-fill');
    var dailyLoss = Math.abs(Math.min(risk.daily_pnl_pct || 0, 0)) * 100;
    if (lossEl) lossEl.textContent = dailyLoss.toFixed(2) + '%';
    if (lossFill) {
        var lossPct = Math.min(dailyLoss / 3 * 100, 100);
        var lcls = dailyLoss < 1.5 ? 'safe' : dailyLoss < 3 ? 'warn' : 'danger';
        lossFill.style.width = lossPct + '%';
        lossFill.className = 'progress-fill ' + lcls;
    }
}

function updateTrades(trades) {
    var tbody = document.getElementById('trades-tbody');
    var countEl = document.getElementById('trades-count');
    if (!tbody) return;
    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无交易记录</td></tr>';
        if (countEl) countEl.textContent = '0 条';
        return;
    }
    var html = '';
    var recent = trades.slice(-10).reverse();
    recent.forEach(function(t) {
        var isBuy = (t.action === 'BUY');
        var actCn = isBuy ? '买入' : '卖出';
        var actColor = isBuy ? 'var(--price-up)' : 'var(--price-down)';
        var pnl = t.pnl || 0;
        var pnlColor = pnl >= 0 ? 'var(--price-up)' : 'var(--price-down)';
        html += '<tr>'
            + '<td>' + esc(t.time || '') + '</td>'
            + '<td><span class="code">' + esc(t.code || '') + '</span></td>'
            + '<td style="color:' + actColor + ';font-weight:600;">' + actCn + '</td>'
            + '<td>' + (t.price ? t.price.toFixed(3) : '--') + '</td>'
            + '<td>' + (t.shares || 0) + '</td>'
            + '<td style="color:' + pnlColor + ';font-weight:600;">' + pnlSign(pnl) + (pnl ? pnl.toFixed(2) : '0.00') + '</td>'
            + '</tr>';
    });
    tbody.innerHTML = html;
    if (countEl) countEl.textContent = trades.length + ' 条';
}

function updateAlerts(alerts) {
    var list = document.getElementById('alerts-list');
    var countEl = document.getElementById('alerts-count');
    if (!list) return;
    if (!alerts || alerts.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无告警</div>';
        if (countEl) countEl.textContent = '0 条';
        return;
    }
    var html = '';
    var recent = alerts.slice(-5).reverse();
    recent.forEach(function(a) {
        var lvl = a.level || 'info';
        html += '<div class="alert-item">'
            + '<span class="alert-badge ' + lvl + '">' + lvl.toUpperCase() + '</span>'
            + '<span class="alert-msg">' + esc(a.code || '') + ' ' + esc(a.message || '') + '</span>'
            + '<span class="alert-time">' + esc(a.time || '') + '</span>'
            + '</div>';
    });
    list.innerHTML = html;
    if (countEl) countEl.textContent = alerts.length + ' 条';
}

function updateTime() {
    var el = document.getElementById('metric-time');
    if (el) el.textContent = new Date().toLocaleString('zh-CN', {hour12: false});
}

// ==================== 启动 ====================
initTheme();
document.addEventListener('DOMContentLoaded', function() {
    fetchAndUpdate();
    refreshTimer = setInterval(fetchAndUpdate, REFRESH_MS);
});
"""

    # ==================== 主组装 ====================

    def _build_html(self, state: dict) -> str:
        """构建完整的HTML仪表盘页面。"""
        # 注入初始数据（服务端渲染，避免首次额外请求）
        initial_data = {
            "status": {
                "status": state.get("status", "running"),
                "capital": state.get("capital", 0),
                "daily_pnl": state.get("daily_pnl", 0),
                "daily_pnl_pct": state.get("daily_pnl_pct", 0),
                "time": state.get("time", ""),
                "last_scan": state.get("last_scan", "--"),
                "scan_count": state.get("scan_count", 0),
            },
            "positions": state.get("positions", {}),
            "signals": state.get("signals", []),
            "risk": state.get("risk", {}),
            "trades": state.get("trades", []),
            "alerts": state.get("alerts", []),
        }

        js_code = self._get_javascript()
        init_inject = f"""
// 初始数据注入（服务端渲染）
cache = {json.dumps(initial_data, ensure_ascii=False)};
document.addEventListener('DOMContentLoaded', function() {{
    updateDOM(cache);
}});
"""
        js_code = init_inject + js_code

        return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股做T量化交易系统 v3.0</title>
<style>
{self._get_theme_css()}
{self._get_layout_css()}
{self._get_component_css()}
</style>
</head>
<body>
{self._get_header_html(state)}
<div class="main-container">
    {self._get_positions_html(state)}
    {self._get_signals_html(state)}
    {self._get_risk_html(state)}
    {self._get_trades_html(state)}
    {self._get_alerts_html(state)}
</div>
{self._get_footer_html(state)}
<script>
{js_code}
</script>
</body>
</html>"""
