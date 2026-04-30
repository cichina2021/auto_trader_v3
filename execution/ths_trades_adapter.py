"""
同花顺 ths_trades WEB API 适配器（默认关闭）

通过HTTP API与 ths_trades 服务通信，实现自动化下单。
ths_trades 需要在Windows虚拟机中部署并运行。

安装: git clone https://github.com/sdasdfasd64565/ths_trades
启动: python app.py（保持运行）
默认端口: 6003
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)


class ThsTradesAdapter:
    """ths_trades WEB API 适配器。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 6003,
                 enabled: bool = False):
        """
        Args:
            host: ths_trades 服务地址
            port: ths_trades 服务端口
            enabled: 是否启用（默认关闭）
        """
        self.host = host
        self.port = port
        self.enabled = enabled
        self.base_url = f"http://{host}:{port}/api"

        if enabled:
            logger.info(f"ths_trades 适配器已启用: {self.base_url}")
        else:
            logger.info("ths_trades 适配器已禁用（使用文件信号模式）")

    def execute(self, code: str, action: str, price: float,
                shares: int, account: str = "default") -> dict:
        """
        通过 ths_trades API 执行交易。

        Args:
            code: 股票代码（如 "002539"）
            action: "BUY" / "SELL"
            price: 委托价格
            shares: 委托数量
            account: 账户标识

        Returns:
            {"success": bool, "method": "ths_trades", "result/error": ...}
        """
        if not self.enabled:
            return {
                "success": False,
                "method": "ths_trades",
                "error": "ths_trades 适配器已禁用，请在config中启用"
            }

        method = "buy" if action == "BUY" else "sell"
        payload = {
            "method": method,
            "account": account,
            "stock_code": code,
            "price": float(price),
            "quantity": int(shares),
            "price_type": "limit",  # 限价委托
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{self.base_url}/queue",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                logger.info(f"ths_trades 下单: {code} {method} "
                           f"{shares}股 @ {price}")
                return {"success": True, "method": "ths_trades", "result": result}

        except urllib.error.URLError as e:
            logger.error(f"ths_trades 连接失败: {e}")
            return {"success": False, "method": "ths_trades",
                    "error": f"连接失败: {e}"}
        except json.JSONDecodeError as e:
            logger.error(f"ths_trades 响应解析失败: {e}")
            return {"success": False, "method": "ths_trades",
                    "error": f"响应解析失败: {e}"}
        except Exception as e:
            logger.error(f"ths_trades 异常: {e}")
            return {"success": False, "method": "ths_trades",
                    "error": str(e)}

    def ping(self) -> bool:
        """检查 ths_trades 服务是否在线。"""
        try:
            req = urllib.request.Request(f"{self.base_url}/ping")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.getcode() == 200
        except Exception:
            return False

    def get_position(self, account: str = "default") -> Optional[dict]:
        """查询当前持仓。"""
        if not self.enabled:
            return None
        try:
            payload = json.dumps({"method": "position", "account": account}).encode()
            req = urllib.request.Request(
                f"{self.base_url}/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"查询持仓失败: {e}")
            return None

    def get_balance(self, account: str = "default") -> Optional[dict]:
        """查询账户余额。"""
        if not self.enabled:
            return None
        try:
            payload = json.dumps({"method": "balance", "account": account}).encode()
            req = urllib.request.Request(
                f"{self.base_url}/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"查询余额失败: {e}")
            return None
