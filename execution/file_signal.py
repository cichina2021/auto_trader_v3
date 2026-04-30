"""
文件信号执行器（默认开启）

将交易信号写入JSON文件，供手动执行或外部程序读取。
适用于：
- 不想自动交易的保守模式
- 跨平台信号传递（如Mac→Windows通过共享文件夹）
- 调试和复盘
"""
import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FileSignalExecutor:
    """基于文件的交易信号执行器。"""

    def __init__(self, signal_dir: str = "trading_signals"):
        """
        Args:
            signal_dir: 信号文件输出目录
        """
        self.signal_dir = signal_dir
        os.makedirs(signal_dir, exist_ok=True)
        logger.info(f"文件信号执行器初始化: 目录={os.path.abspath(signal_dir)}")

    def execute(self, code: str, action: str, price: float,
                shares: int, reason: str = "") -> dict:
        """
        写入信号文件。

        Args:
            code: 股票代码
            action: BUY / SELL
            price: 目标价格
            shares: 股数
            reason: 信号原因

        Returns:
            {"success": bool, "method": "file_signal", "file": str}
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{action}_{code}_{timestamp}.json"
        filepath = os.path.join(self.signal_dir, filename)

        signal = {
            "code": code,
            "action": action,
            "action_cn": "买入" if action == "BUY" else "卖出",
            "price": price,
            "shares": shares,
            "amount": round(price * shares, 2),
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(signal, f, ensure_ascii=False, indent=2)
            logger.info(f"信号文件已写入: {filepath}")
            return {"success": True, "method": "file_signal", "file": filepath}
        except Exception as e:
            logger.error(f"写入信号文件失败: {e}")
            return {"success": False, "method": "file_signal", "error": str(e)}

    def list_pending(self) -> list:
        """列出所有待执行的信号文件。"""
        pending = []
        if not os.path.exists(self.signal_dir):
            return pending

        for filename in os.listdir(self.signal_dir):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(self.signal_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("status") == "pending":
                        data["file"] = filepath
                        pending.append(data)
            except Exception:
                continue

        return pending

    def mark_executed(self, filepath: str, result: str = "done"):
        """标记信号文件为已执行。"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data["status"] = result
            data["executed_at"] = datetime.now().isoformat()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"标记信号失败: {e}")
