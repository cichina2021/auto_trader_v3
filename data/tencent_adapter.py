"""
腾讯财经数据适配器
通过腾讯公开HTTP API获取A股行情（第三备用数据源）
主要提供分钟级K线数据（新浪不支持的周期）
"""
import re
import time
import json
import logging
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class TencentAdapter:
    """腾讯财经行情数据适配器（分钟K线数据源）"""

    NAME = "tencent"

    def __init__(self):
        self._available = True

    def is_available(self) -> bool:
        return True

    @staticmethod
    def _headers() -> dict:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.qq.com',
        }

    @staticmethod
    def _http_get(url: str, timeout: int = 10) -> Optional[str]:
        import urllib.request
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=TencentAdapter._headers())
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode('utf-8', errors='replace')
            except Exception as e:
                logger.debug(f"腾讯请求失败(尝试{attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(1)
                else:
                    return None

    @staticmethod
    def _parse_code(code: str) -> str:
        """将股票代码转为腾讯格式 (sh600519 / sz002539)"""
        code = code.strip().upper()
        # 已经是腾讯/新浪格式
        if code.startswith('SH') or code.startswith('SZ') or \
           code.startswith('sh') or code.startswith('sz'):
            return code.lower()
        num = code.zfill(6)
        if num.startswith('6'):
            return 'sh' + num
        else:
            return 'sz' + num

    def get_realtime(self, codes: List[str]) -> List[dict]:
        """
        批量获取实时行情（腾讯接口）

        Returns:
            行情字典列表: {code, name, price, open, high, low,
                           volume, amount, change_pct}
        """
        if not codes:
            return []

        tc_codes = [self._parse_code(c) for c in codes]
        codes_str = ','.join(tc_codes)
        url = f"https://qt.gtimg.cn/q={codes_str}"

        text = self._http_get(url, timeout=15)
        if not text:
            return []

        result = []
        # 腾讯格式: v_sh002539="..." → 匹配 sh002539
        pattern = r'_([a-z]{2})(\d{6})="([^"]*)"'
            parts = content.split('~')
            if len(parts) < 45:
                continue
            try:
                prev_close = float(parts[4]) if parts[4] else 0
                price = float(parts[3]) if parts[3] else prev_close
                quote = {
                    "code": code.zfill(6),
                    "name": parts[1] if len(parts) > 1 else "",
                    "price": price,
                    "prev_close": prev_close,
                    "open": float(parts[5]) if len(parts) > 5 and parts[5] else price,
                    "high": float(parts[33]) if len(parts) > 33 and parts[33] else price,
                    "low": float(parts[34]) if len(parts) > 34 and parts[34] else price,
                    "volume": float(parts[36]) if len(parts) > 36 and parts[36] else 0,
                    "amount": float(parts[37]) if len(parts) > 37 and parts[37] else 0,
                    "change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0,
                }
                result.append(quote)
            except (ValueError, IndexError):
                continue

        logger.debug(f"腾讯获取{len(tc_codes)}只，命中{len(result)}条")
        return result

    def get_kline(self, code: str, period: str = "daily",
                  count: int = 120) -> Optional[pd.DataFrame]:
        """
        获取K线数据（腾讯接口，支持多周期）

        Args:
            code: 股票代码
            period: 周期 ("daily" / "60m" / "15m" / "5m")
            count: 条数
        """
        tc_code = self._parse_code(code)

        freq_map = {
            "1m": "1", "5m": "5", "15m": "15",
            "30m": "30", "60m": "60", "daily": "day",
        }
        qt_freq = freq_map.get(period, "day")

        if qt_freq == "day":
            url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                   f"?_var=kline_dayqfq"
                   f"&param={tc_code},day,,,{count},qfq")
        else:
            url = (f"https://web.ifzq.gtimg.cn/appstock/app/kline/mkline"
                   f"?param={tc_code},m{qt_freq},{count}")

        text = self._http_get(url)
        if not text:
            return None

        try:
            text = re.sub(r'^[^{]*', '', text.strip())
            data = json.loads(text)

            records = []
            if qt_freq == "day":
                qfqday = data.get("data", {}).get(tc_code, {}).get("qfqday", [])
                for item in qfqday[-count:]:
                    if isinstance(item, list) and len(item) >= 6:
                        records.append({
                            "date": str(item[0]),
                            "open": float(item[1]),
                            "close": float(item[2]),
                            "high": float(item[3]),
                            "low": float(item[4]),
                            "volume": float(item[5]),
                            "amount": float(item[5]) * float(item[2]) if len(item) > 2 else 0,
                        })
            else:
                mdata = data.get("data", {}).get(tc_code, {}).get("m" + qt_freq, [])
                for item in mdata[-count:]:
                    if isinstance(item, list) and len(item) >= 6:
                        records.append({
                            "date": str(item[0]),
                            "open": float(item[1]),
                            "close": float(item[2]),
                            "high": float(item[3]),
                            "low": float(item[4]),
                            "volume": float(item[5]),
                            "amount": float(item[5]) * float(item[2]),
                        })

            df = pd.DataFrame(records)
            logger.debug(f"腾讯K线[{code}/{period}]获取{len(df)}条")
            return df if len(df) > 0 else None

        except Exception as e:
            logger.error(f"腾讯K线解析失败 [{code}/{period}]: {e}")
            return None
