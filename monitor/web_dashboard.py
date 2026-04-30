"""
专业Web监控面板

通过Python内置HTTP服务器提供Web界面，无需Flask等外部依赖。
包含完整的实时监控仪表盘和REST API。

A股配色规则：红涨绿跌
暗色主题，专业金融终端风格
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
    Web监控面板HTTP处理器。

    get_state 为类级别回调，由TradingSystem在启动时注入。
    """

    def __init__(self, *args, **kwargs):
        self.get_state = getattr(self.__class__, 'get_state', lambda: {})
        super().__init__(*args, **kwargs)

    # 静默日志
    def log_message(self, format, *args):
        logger.debug(f"HTTP: {format % args}")

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

    def _handle_dashboard(self):
        """渲染完整HTML仪表盘。"""
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

    def _send_response(self, code: int, content_type: str, body: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _build_html(self, state: dict) -> str:
        """构建完整的HTML仪表盘页面。"""
        status = state.get("status", "running")
        status_color = "#3fb950" if status == "running" else "#f85149"
        status_text = "运行中" if status == "running" else "已暂停"
        current_time = state.get("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        capital = state.get("capital", 0)
        daily_pnl = state.get("daily_pnl", 0)
        daily_pnl_pct = state.get("daily_pnl_pct", 0)
        pnl_color = "#f85149" if daily_pnl >= 0 else "#3fb950"  # A股：红涨
        pnl_sign = "+" if daily_pnl >= 0 else ""
        last_scan = state.get("last_scan", "--")

        # 风控指标
        risk = state.get("risk", {})
        var_val = risk.get("var", 0)
        kelly_frac = risk.get("kelly_fraction", 0)
        win_rate = risk.get("win_rate", 0)
        total_trades = risk.get("total_trades", 0)
        is_halted = risk.get("is_halted", False)

        # 仓位表格
        positions = state.get("positions", {})
        positions_rows = ""
        for code, pos in positions.items():
            name = pos.get("name", code)
            t_held = pos.get("t_held", 0)
            t_cost = pos.get("t_cost", 0)
            t_max = pos.get("t_max", 0)
            today_trades = pos.get("today_trades", 0)
            positions_rows += f"""
            <tr>
                <td><span class="code">{code}</span></td>
                <td>{name}</td>
                <td>{t_max}</td>
                <td>{t_held}</td>
                <td>{t_cost:.3f}</td>
                <td>{today_trades}</td>
            </tr>"""

        # 信号面板
        signals = state.get("signals", [])
        signals_html = ""
        for s in signals:
            action = s.get("action", "")
            is_buy = action == "BUY"
            color = "#f85149" if is_buy else "#3fb950"
            action_cn = "买入" if is_buy else "卖出"
            confidence = s.get("confidence", 0)
            signals_html += f"""
            <div class="signal-card" style="border-left:3px solid {color}">
                <div class="signal-header">
                    <span class="signal-code">{s.get('code','')}</span>
                    <span class="signal-action" style="color:{color}">{action_cn}</span>
                    <span class="signal-confidence">置信度 {confidence:.0%}</span>
                </div>
                <div class="signal-detail">
                    价格: {s.get('price',0):.2f} | {s.get('reason','')}
                </div>
            </div>"""

        if not signals_html:
            signals_html = '<div class="empty-state">暂无信号</div>'

        # 交易记录
        trades = state.get("trades", [])
        trades_rows = ""
        for t in reversed(trades[-10:]):
            pnl = t.get("pnl", 0)
            pnl_color = "#f85149" if pnl >= 0 else "#3fb950"
            action = t.get("action", "")
            action_cn = "买入" if action == "BUY" else "卖出"
            trades_rows += f"""
            <tr>
                <td>{t.get('time','')}</td>
                <td>{t.get('code','')}</td>
                <td style="color:{'#f85149' if action=='BUY' else '#3fb950'}">{action_cn}</td>
                <td>{t.get('price',0):.3f}</td>
                <td>{t.get('shares',0)}</td>
                <td style="color:{pnl_color}">{pnl:+.2f}</td>
            </tr>"""

        if not trades_rows:
            trades_rows = '<tr><td colspan="6" class="empty-state">暂无交易记录</td></tr>'

        # 告警面板
        alerts = state.get("alerts", [])
        alerts_html = ""
        for a in reversed(alerts[-5:]):
            level = a.get("level", "info")
            level_color = {"critical": "#f85149", "warning": "#d29922", "info": "#58a6ff"}.get(level, "#8b949e")
            alerts_html += f"""
            <div class="alert-item" style="border-left:3px solid {level_color}">
                <span class="alert-level" style="color:{level_color}">[{level.upper()}]</span>
                <span class="alert-msg">{a.get('code','')} {a.get('message','')}</span>
                <span class="alert-time">{a.get('time','')}</span>
            </div>"""

        if not alerts_html:
            alerts_html = '<div class="empty-state">暂无告警</div>'

        # VaR进度条
        var_pct = min(var_val * 100, 10)
        var_bar_color = "#3fb950" if var_val < 0.015 else "#d29922" if var_val < 0.03 else "#f85149"

        # 日亏损进度条
        daily_loss_pct = abs(min(daily_pnl_pct, 0)) * 100
        loss_bar_color = "#3fb950" if daily_loss_pct < 1.5 else "#d29922" if daily_loss_pct < 3 else "#f85149"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="30">
<title>A股做T量化交易系统 v3.0</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #0d1117; color: #c9d1d9; line-height: 1.6;
    padding: 20px;
}}
.header {{
    display: flex; align-items: center; justify-content: space-between;
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 16px 24px; margin-bottom: 20px;
}}
.header-left {{ display: flex; align-items: center; gap: 20px; }}
.logo {{ font-size: 20px; font-weight: 700; color: #f0f6fc; }}
.status-badge {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 20px; font-size: 13px;
    background: {status_color}20; color: {status_color}; border: 1px solid {status_color}40;
}}
.status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {status_color};
    animation: pulse 2s infinite; }}
@keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}
.header-metrics {{ display: flex; gap: 24px; }}
.metric {{ text-align: center; }}
.metric-label {{ font-size: 11px; color: #8b949e; text-transform: uppercase; }}
.metric-value {{ font-size: 20px; font-weight: 700; color: #f0f6fc; }}
.metric-value.pnl {{ color: {pnl_color}; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
.card {{
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 20px;
}}
.card-title {{
    font-size: 14px; font-weight: 600; color: #8b949e;
    margin-bottom: 16px; display: flex; align-items: center; gap: 8px;
}}
.card-title::before {{ content: ''; width: 3px; height: 14px; background: #58a6ff;
    border-radius: 2px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 8px 12px; color: #8b949e; font-weight: 500;
    border-bottom: 1px solid #30363d; font-size: 11px; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #21262d; }}
.code {{ color: #79c0ff; font-weight: 600; font-family: monospace; }}
.signal-card {{
    background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
    padding: 12px; margin-bottom: 8px;
}}
.signal-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }}
.signal-code {{ color: #79c0ff; font-weight: 600; font-family: monospace; }}
.signal-action {{ font-weight: 700; }}
.signal-confidence {{ color: #8b949e; font-size: 12px; margin-left: auto; }}
.signal-detail {{ color: #8b949e; font-size: 12px; }}
.risk-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.risk-item {{ background: #0d1117; border-radius: 8px; padding: 12px; }}
.risk-label {{ font-size: 11px; color: #8b949e; margin-bottom: 4px; }}
.risk-value {{ font-size: 18px; font-weight: 700; }}
.progress-bar {{ height: 6px; background: #21262d; border-radius: 3px; margin-top: 6px; overflow: hidden; }}
.progress-fill {{ height: 100%; border-radius: 3px; transition: width 0.5s; }}
.alert-item {{
    background: #0d1117; border-radius: 6px; padding: 10px 12px;
    margin-bottom: 6px; display: flex; align-items: center; gap: 8px; font-size: 12px;
}}
.alert-level {{ font-weight: 700; font-size: 11px; }}
.alert-msg {{ flex: 1; color: #c9d1d9; }}
.alert-time {{ color: #484f58; }}
.empty-state {{ color: #484f58; text-align: center; padding: 20px; font-size: 13px; }}
.footer {{
    text-align: center; padding: 16px; color: #484f58; font-size: 12px;
    border-top: 1px solid #21262d; margin-top: 20px;
}}
.full-width {{ grid-column: 1 / -1; }}
</style>
</head>
<body>
<div class="header">
    <div class="header-left">
        <div class="logo">A股做T量化系统 v3.0</div>
        <div class="status-badge">
            <span class="status-dot"></span>
            {status_text}
        </div>
    </div>
    <div class="header-metrics">
        <div class="metric">
            <div class="metric-label">总资金</div>
            <div class="metric-value">{capital:,.0f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">今日盈亏</div>
            <div class="metric-value pnl">{pnl_sign}{daily_pnl:,.2f} ({daily_pnl_pct:+.2%})</div>
        </div>
        <div class="metric">
            <div class="metric-label">更新时间</div>
            <div class="metric-value" style="font-size:14px;">{current_time}</div>
        </div>
    </div>
</div>

<div class="grid">
    <!-- 持仓面板 -->
    <div class="card">
        <div class="card-title">持仓监控</div>
        <table>
            <thead><tr>
                <th>代码</th><th>名称</th><th>T仓上限</th>
                <th>T仓持有</th><th>T仓成本</th><th>今日交易</th>
            </tr></thead>
            <tbody>{positions_rows if positions_rows else '<tr><td colspan="6" class="empty-state">暂无持仓</td></tr>'}</tbody>
        </table>
    </div>

    <!-- 信号面板 -->
    <div class="card">
        <div class="card-title">交易信号</div>
        {signals_html}
    </div>

    <!-- 风控面板 -->
    <div class="card">
        <div class="card-title">风控指标</div>
        <div class="risk-grid">
            <div class="risk-item">
                <div class="risk-label">VaR (95%)</div>
                <div class="risk-value">{var_val:.2%}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:{var_pct * 10}%;background:{var_bar_color}"></div>
                </div>
            </div>
            <div class="risk-item">
                <div class="risk-label">Kelly分数</div>
                <div class="risk-value">{kelly_frac:.0%}</div>
            </div>
            <div class="risk-item">
                <div class="risk-label">历史胜率</div>
                <div class="risk-value">{win_rate:.1%}</div>
            </div>
            <div class="risk-item">
                <div class="risk-label">今日交易</div>
                <div class="risk-value">{total_trades}</div>
            </div>
            <div class="risk-item" style="grid-column: 1 / -1;">
                <div class="risk-label">日亏损进度 (硬停3%)</div>
                <div class="risk-value" style="color:{pnl_color}">{daily_loss_pct:.2%}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:{daily_loss_pct}%;background:{loss_bar_color}"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- 交易记录 -->
    <div class="card">
        <div class="card-title">交易记录</div>
        <table>
            <thead><tr>
                <th>时间</th><th>代码</th><th>方向</th>
                <th>价格</th><th>股数</th><th>盈亏</th>
            </tr></thead>
            <tbody>{trades_rows}</tbody>
        </table>
    </div>

    <!-- 告警面板 -->
    <div class="card full-width">
        <div class="card-title">系统告警</div>
        {alerts_html}
    </div>
</div>

<div class="footer">
    A股做T量化交易系统 v3.0 | 最后扫描: {last_scan} |
    自动刷新间隔: 30秒 | <a href="/api/status" style="color:#58a6ff;">API</a>
</div>
</body>
</html>"""
