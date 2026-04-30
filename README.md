# A股专业做T量化交易系统 v3.0
# 
# ## 系统架构
# 四层分离架构:
#   data/         → 数据层 (akshare→新浪→腾讯, 三级容错+TTL缓存)
#   strategy/     → 策略层 (4大因子 + 贝叶斯融合 + 多周期MACD共振)
#   risk/         → 风控层 (Kelly仓位 + VaR + ATR止损 + 多层限额)
#   execution/    → 执行层 (文件信号输出 / ths_trades API)
#   backtest/     → 回测层 (事件驱动 + 成本模型 + T+1约束)
#   monitor/      → 监控层 (Web面板 + 日志 + 告警)
#
# ## 核心能力
# - 多股票支持（不再绑定单一标的）
# - 贝叶斯信号融合（先验→似然→后验）
# - Kelly公式动态仓位管理
# - VaR 95%风险价值实时监控
# - 多周期MACD共振确认（日/60m/15m/5m）
# - 完整事件驱动回测引擎
# - 专业Web监控仪表盘（端口8080）
#
# ## 启动方式
# python main.py              # 信号模式 + Web监控面板
# python main.py --backtest   # 历史回测
#
# ## 数据源依赖
# pip install akshare numpy pandas
