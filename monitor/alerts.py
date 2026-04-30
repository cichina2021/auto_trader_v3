"""
告警系统

管理交易系统的告警信息：
- 风控触发告警
- 异常交易告警
- 数据源异常告警
- 系统状态告警
"""
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class AlertManager:
    """告警管理器。"""

    # 告警级别
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def __init__(self, max_alerts: int = 200):
        """
        Args:
            max_alerts: 最大保留告警数量
        """
        self.alerts: List[dict] = []
        self.max_alerts = max_alerts
        self.alert_logger = logging.getLogger("alerts")

    def add_alert(self, level: str, code: str, message: str):
        """
        添加告警。

        Args:
            level: 告警级别 ("info"/"warning"/"critical")
            code: 关联的股票代码（或"SYSTEM"表示系统级）
            message: 告警消息
        """
        alert = {
            "level": level,
            "code": code,
            "message": message,
            "time": datetime.now().strftime("%H:%M:%S"),
            "read": False,
        }
        self.alerts.append(alert)

        # 限制数量
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]

        # 日志输出
        if level == "critical":
            self.alert_logger.critical(f"[{code}] {message}")
        elif level == "warning":
            self.alert_logger.warning(f"[{code}] {message}")
        else:
            self.alert_logger.info(f"[{code}] {message}")

    def add_risk_alert(self, code: str, message: str):
        """风控告警。"""
        self.add_alert(self.WARNING, code, f"[风控] {message}")

    def add_halt_alert(self, reason: str):
        """系统暂停告警。"""
        self.add_alert(self.CRITICAL, "SYSTEM", f"系统暂停: {reason}")

    def add_data_alert(self, message: str):
        """数据异常告警。"""
        self.add_alert(self.WARNING, "SYSTEM", f"[数据] {message}")

    def add_trade_alert(self, code: str, action: str, price: float,
                        shares: int, reason: str):
        """交易执行告警。"""
        action_cn = "买入" if action == "BUY" else "卖出"
        self.add_alert(
            self.INFO, code,
            f"执行{action_cn}: {shares}股 @ {price:.3f} | {reason}"
        )

    def get_unread(self) -> List[dict]:
        """获取未读告警。"""
        return [a for a in self.alerts if not a["read"]]

    def get_recent(self, limit: int = 20) -> List[dict]:
        """获取最近的告警。"""
        return self.alerts[-limit:]

    def get_by_level(self, level: str) -> List[dict]:
        """获取指定级别的告警。"""
        return [a for a in self.alerts if a["level"] == level]

    def mark_all_read(self):
        """标记所有告警为已读。"""
        for alert in self.alerts:
            alert["read"] = True

    def mark_read(self, index: int):
        """标记指定告警为已读。"""
        if 0 <= index < len(self.alerts):
            self.alerts[index]["read"] = True

    def clear(self):
        """清空所有告警。"""
        self.alerts.clear()

    def get_stats(self) -> dict:
        """获取告警统计。"""
        unread = len(self.get_unread())
        critical = len(self.get_by_level("critical"))
        warnings = len(self.get_by_level("warning"))
        return {
            "total": len(self.alerts),
            "unread": unread,
            "critical": critical,
            "warnings": warnings,
        }
