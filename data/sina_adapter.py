"""
新浪财经数据适配器
通过新浪公开HTTP API获取A股行情（备用数据源）
"""
import re
import time
import json
import logging
from typing import List, Optional
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class SinaAdapter:
    """新浪财经行情数据适配器（备用数据源）"""

    NAME = "sina"

    def __init__(self):
        self._available = True  # 新浪API无需依赖，始终可用

    def is_available(self) -> bool:
        return True

    @staticmethod
    def _headers() -> dict:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn',
        }

    @staticmethod
    def _http_get(url: str, timeout: int = 10) -> Optional[str]:
        """带重试的HTTP GET"""
        import urllib.request
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=SinaAdapter._headers())
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode('gbk', errors='replace')
            except Exception as e:
                logger.debug(f"新浪请求失败(尝试{attempt+1}): {e}")
                if attempt < 2:
                    time.sleep(1)
                else:
                    return None

    @staticmethod
    def _parse_code(code: str) -> str:
        """将股票代码转为新浪格式 (sh600519 / sz002539)"""
        code = code.strip().upper()
        # 已经是新浪格式
        if code.startswith('SH') or code.startswith('SZ') or \
           code.startswith('sh') or code.startswith('sz'):
            return code.lower()
        # 纯数字格式
        num = code.zfill(6)
        if num.startswith('6') or num == '000001':
            return 'sh' + num
        else:
            return 'sz' + num

    def get_realtime(self, codes: List[str]) -> List[dict]:
        """
        批量获取实时行情（新浪接口）

        Returns:
            行情字典列表: {code, name, price, open, high, low, volume,
                           amount, change_pct, prev_close}
        """
        if not codes:
            return []

        sina_codes = [self._parse_code(c) for c in codes]
        codes_str = ','.join(sina_codes)
        url = f"https://hq.sinajs.cn/list={codes_str}"

        text = self._http_get(url, timeout=15)
        if not text:
            return []

        result = []
        pattern = r'hq_str_[a-z]{2}(\d+)="([^"]*)"'
        matches = re.findall(pattern, text)

        for code, content in matches:
            parts = content.split(',')
            if len(parts) < 32:
                continue
            try:
                prev_close = float(parts[2]) if parts[2] else 0
                price = float(parts[3]) if len(parts) > 3 and parts[3] else prev_close
                quote = {
                    "code": code.zfill(6),
                    "name": parts[0] if parts[0] else "",
                    "price": price,
                    "prev_close": prev_close,
                    "open": float(parts[1]) if parts[1] else price,
                    "high": float(parts[4]) if len(parts) > 4 and parts[4] else price,
                    "low": float(parts[5]) if len(parts) > 5 and parts[5] else price,
                    "volume": float(parts[8]) if len(parts) > 8 and parts[8] else 0,
                    "amount": float(parts[9]) if len(parts) > 9 and parts[9] else 0,
                    "change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0,
                }
                result.append(quote)
            except (ValueError, IndexError):
                continue

        logger.debug(f"新浪获取{len(sina_codes)}只，命中{len(result)}条")
        return result

    def get_kline(self, code: str, period: str = "daily",
                  count: int = 120) -> Optional[pd.DataFrame]:
        """
        获取K线数据（新浪JS接口）

        Args:
            code: 股票代码
            period: 周期 ("daily" / 其他周期降级到腾讯)
            count: 条数
        """
        sina_code = self._parse_code(code)

        # 新浪仅支持日线/周线/月线
        if period != "daily":
            logger.debug(f"新浪不支持{period}周期K线")
            return None

        url = (f"https://finance.sina.com.cn/realstock/company/{sina_code}"
               f"/hisdata/klc_kl.js?d={count}")

        text = self._http_get(url)
        if not text:
            return None

        try:
            match = re.search(r'=\s*(\[.*?\]);?\s*$', text, re.DOTALL)
            if not match:
                return None

            data = json.loads(match.group(1))
            records = []
            for item in data:
                records.append({
                    "date": item.get("date", ""),
                    "open": float(item.get("open", 0)),
                    "close": float(item.get("close", 0)),
                    "high": float(item.get("high", 0)),
                    "low": float(item.get("low", 0)),
                    "volume": float(item.get("volume", 0)),
                    "amount": float(item.get("amount", 0)),
                })

            df = pd.DataFrame(records)
            logger.debug(f"新浪K线[{code}/daily]获取{len(df)}条")
            return df.tail(count).reset_index(drop=True)

        except Exception as e:
            logger.error(f"新浪K线解析失败 [{code}]: {e}")
            return None
