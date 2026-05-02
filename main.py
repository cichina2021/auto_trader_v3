"""
A股专业做T量化交易系统 v3.0 — 主入口

四层架构：
  数据层 → 策略层 → 风控层 → 执行层
  + 监控层(Web面板) + 回测层

使用方法：
  python main.py              # 正常启动（信号模式 + Web面板）
  python main.py --backtest   # 运行历史回测
"""
import sys
import os
import time
import signal as sig_module
import logging
import threading
import argparse
from datetime import datetime
from http.server import HTTPServer

# 确保项目根目录在Python路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from config.settings import (
    POSITIONS, EXECUTION, HTTP_PORT, LOOP_INTERVAL,
    LOG_DIR, LOG_LEVEL,
)
from config.risk_params import INITIAL_CAPITAL
from data.datasource import DataSourceManager
from strategy.engine import StrategyEngine
from risk.manager import RiskManager
from risk.position import PositionManager
from execution.executor import ExecutionManager
from execution.order_manager import OrderManager
from execution.file_signal import FileSignalExecutor
from execution.ths_trades_adapter import ThsTradesAdapter
from monitor.web_dashboard import DashboardHandler
from monitor.logger import setup_logger
from monitor.alerts import AlertManager

logger = logging.getLogger("auto_trader")


class TradingSystem:
    """A股做T量化交易系统 — 主协调器。"""

    def __init__(self):
        # 初始化日志
        self.logger = setup_logger("auto_trader", LOG_DIR, LOG_LEVEL)
        self.logger.info("=" * 60)
        self.logger.info("  A股做T量化交易系统 v3.0")
        self.logger.info("  启动时间: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.logger.info("=" * 60)

        # 第1层: 数据层
        self.logger.info("[数据层] 初始化...")
        self.data_source = DataSourceManager()

        # 第2层: 仓位管理 + 风控
        self.logger.info("[仓位管理] 初始化...")
        self.position_manager = PositionManager()

        self.logger.info("[风控层] 初始化 (Kelly + VaR + 多层限额)...")
        self.risk_manager = RiskManager(INITIAL_CAPITAL)

        self.logger.info("[策略层] 初始化 (多因子 + 贝叶斯融合)...")
        self.strategy_engine = StrategyEngine()

        # 第3层: 执行层
        self.logger.info("[执行层] 初始化...")
        self.order_manager = OrderManager()
        self.file_signal = FileSignalExecutor(
            EXECUTION.get("signal_dir", "trading_signals")
        )
        self.ths_trades = ThsTradesAdapter(
            host=EXECUTION.get("ths_web_host", "127.0.0.1"),
            port=EXECUTION.get("ths_web_port", 6003),
            enabled=EXECUTION.get("mode") == "live",
        )
        self.execution = ExecutionManager(
            self.risk_manager,
            self.position_manager,
            self.order_manager,
            self.file_signal,
            self.ths_trades,
        )

        # 第4层: 监控层
        self.logger.info("[监控层] 初始化...")
        self.alerts = AlertManager()

        # 系统状态
        self.running = True
        self.signals = []
        self.last_scan_time = None
        self.scan_count = 0

        # 优雅关闭
        sig_module.signal(sig_module.SIGINT, self._shutdown)
        sig_module.signal(sig_module.SIGTERM, self._shutdown)

        self.logger.info("系统初始化完成")

    def _shutdown(self, signum, frame):
        """信号处理：优雅关闭。"""
        self.logger.info("收到停止信号 (%s)，正在安全关闭...", signum)
        self.running = False

    def get_system_state(self) -> dict:
        """返回完整系统状态（供Web面板使用）。"""
        risk_status = self.risk_manager.get_status()
        exec_status = self.execution.get_status()

        return {
            "status": "halted" if self.risk_manager.is_halted else "running",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "capital": self.risk_manager.capital,
            "daily_pnl": risk_status.get("daily_pnl", 0),
            "daily_pnl_pct": risk_status.get("daily_pnl_pct", 0),
            "positions": risk_status.get("positions", {}),
            "signals": [
                {
                    "code": s.code if hasattr(s, 'code') else s.get('code', ''),
                    "action": s.action if hasattr(s, 'action') else s.get('action', ''),
                    "price": s.price if hasattr(s, 'price') else s.get('price', 0),
                    "confidence": s.confidence if hasattr(s, 'confidence') else s.get('confidence', 0),
                    "reason": s.reason if hasattr(s, 'reason') else s.get('reason', ''),
                }
                for s in self.signals
            ],
            "risk": risk_status,
            "trades": [
                {
                    "time": t.get("time", ""),
                    "code": t.get("code", ""),
                    "action": t.get("action", ""),
                    "price": t.get("price", 0),
                    "shares": t.get("shares", 0),
                    "pnl": t.get("pnl", 0),
                }
                for t in self.risk_manager.trade_history[-20:]
            ],
            "alerts": self.alerts.get_recent(10),
            "last_scan": self.last_scan_time or "--",
            "execution": exec_status,
            "scan_count": self.scan_count,
        }

    def scan_and_trade(self):
        """主扫描周期：获取信号 → 风控检查 → 执行。"""
        codes = list(POSITIONS.keys())
        if not codes:
            self.logger.warning("无跟踪股票，跳过扫描")
            return

        self.scan_count += 1
        self.logger.info(f"--- 第 {self.scan_count} 轮扫描 ({len(codes)} 只股票) ---")

        try:
            # 获取所有股票的信号
            new_signals = self.strategy_engine.evaluate_batch(codes)
            self.signals = new_signals

            if not new_signals:
                self.logger.info("本轮无信号产生")
                return

            # 按置信度排序，优先执行高置信信号
            for signal in new_signals:
                code = signal.code
                action = signal.action
                price = signal.price
                reason = signal.reason

                self.logger.info(
                    f"信号: {code} {action} @ {price:.2f} "
                    f"置信度={signal.confidence:.0%} "
                    f"| {reason}"
                )

                # Kelly公式计算最优仓位
                shares = self.risk_manager.calculate_position_size(code, price)
                if shares <= 0:
                    shares = signal.shares
                if shares <= 0:
                    self.logger.info(f"仓位计算为0，跳过 {code}")
                    continue

                # 执行交易
                result = self.execution.execute_signal_direct(
                    code, action, price, shares, reason
                )

                if result.get("success"):
                    self.alerts.add_trade_alert(
                        code, action, price, shares, reason
                    )
                    self.logger.info(f"执行成功: {result}")
                else:
                    self.logger.warning(f"执行失败: {result.get('error', 'unknown')}")

        except Exception as e:
            self.logger.error(f"扫描异常: {e}", exc_info=True)
            self.alerts.add_data_alert(f"扫描异常: {e}")

        self.last_scan_time = datetime.now().strftime("%H:%M:%S")

    def run(self):
        """启动主循环。"""
        # 启动Web监控面板
        try:
            server = HTTPServer(("0.0.0.0", HTTP_PORT), DashboardHandler)
            # 注入状态回调
            DashboardHandler.get_state = lambda self_handler: self.get_system_state()

            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            self.logger.info(f"Web监控面板: http://localhost:{HTTP_PORT}")
        except Exception as e:
            self.logger.error(f"Web面板启动失败: {e}")
            server = None

        self.logger.info("=" * 60)
        self.logger.info("系统启动完成，进入主循环")
        self.logger.info(f"跟踪股票: {list(POSITIONS.keys())}")
        self.logger.info("=" * 60)

        # 主循环
        while self.running:
            try:
                if DataSourceManager.is_trading_time():
                    self.scan_and_trade()
                    time.sleep(LOOP_INTERVAL)
                else:
                    self.logger.debug("非交易时间，低频扫描")
                    time.sleep(300)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(60)

        # 关闭
        if server:
            server.shutdown()
        self.logger.info("系统已安全关闭")


def run_backtest():
    """运行历史回测。"""
    logger = setup_logger("backtest", "logs", logging.INFO)
    logger.info("=" * 60)
    logger.info("  回测模式")
    logger.info("=" * 60)

    from backtest.engine import BacktestEngine

    engine = BacktestEngine(initial_capital=INITIAL_CAPITAL)

    for code, pos_config in POSITIONS.items():
        name = pos_config.get("name", code)
        base_shares = pos_config.get("base_shares", 0)
        base_cost = pos_config.get("base_cost", 0)
        t_shares = pos_config.get("t_shares", 2400)

        logger.info(f"\n{'='*40}")
        logger.info(f"回测: {name}({code})")
        logger.info(f"底仓: {base_shares}股 @ {base_cost}, T仓上限: {t_shares}")
        logger.info(f"{'='*40}")

        result = engine.run(
            code=code,
            start_date="2025-01-01",
            end_date="2025-12-31",
            lookback=60,
            base_shares=base_shares,
            base_cost=base_cost,
            t_shares=t_shares,
        )

        if "error" in result:
            logger.error(f"回测失败 {code}: {result['error']}")
            continue

        # 打印结果
        logger.info(f"\n回测结果: {name}({code})")
        logger.info(f"  评级: {result.get('grade', 'N/A')}")
        logger.info(f"  年化收益: {result.get('annual_return_pct', 0):.2f}%")
        logger.info(f"  最大回撤: {result.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"  Sharpe: {result.get('sharpe_ratio', 0):.2f}")
        logger.info(f"  Calmar: {result.get('calmar_ratio', 0):.2f}")
        logger.info(f"  胜率: {result.get('win_rate', 0):.2%}")
        logger.info(f"  盈亏比: {result.get('profit_factor', 0):.2f}")
        logger.info(f"  总交易: {result.get('total_trades', 0)}次")
        logger.info(f"  总盈亏: ¥{result.get('total_pnl', 0):.2f}")

        engine.reset()


def main():
    """程序入口。"""
    parser = argparse.ArgumentParser(description="A股做T量化交易系统 v3.0")
    parser.add_argument("--backtest", action="store_true", help="运行历史回测")
    args = parser.parse_args()

    if args.backtest:
        run_backtest()
    else:
        system = TradingSystem()
        system.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，程序退出。")
        sys.exit(0)
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"程序启动失败!")
        print(f"{'='*60}")
        print(f"错误: {type(e).__name__}: {e}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        print(f"\n请将以上错误信息截图反馈。")
        input("\n按回车键退出...")
        sys.exit(1)
