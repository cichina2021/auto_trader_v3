"""
AutoTrader V3 桌面GUI - tkinter版本

简洁实用的交易监控界面，实时显示：
- 系统状态
- 持仓信息
- 交易信号
- 风险指标
- 交易记录
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
from datetime import datetime


class TradingGUI:
    """交易监控GUI主窗口"""
    
    def __init__(self, trading_system=None):
        self.root = tk.Tk()
        self.root.title("AutoTrader V3 - A股做T量化交易系统")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # 保存交易系统引用
        self.trading_system = trading_system
        self.running = True
        
        # 配色方案（暗色主题）
        self.colors = {
            'bg': '#1a1a2e',
            'bg_secondary': '#16213e',
            'accent': '#0f3460',
            'text': '#eee',
            'text_secondary': '#aaa',
            'up': '#ff4d4d',      # A股红色涨（买）
            'down': '#00cc66',    # A股绿色跌（卖）
            'border': '#2d3748'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # 创建界面
        self._create_menu()
        self._create_main_layout()
        self._create_status_bar()
        
        # 启动数据刷新线程
        self.refresh_thread = threading.Thread(target=self._auto_refresh, daemon=True)
        self.refresh_thread.start()
        
        # 窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 系统菜单
        system_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="系统", menu=system_menu)
        system_menu.add_command(label="启动交易", command=self._start_trading)
        system_menu.add_command(label="停止交易", command=self._stop_trading)
        system_menu.add_separator()
        system_menu.add_command(label="管理持仓...", command=self._manage_positions)
        system_menu.add_separator()
        system_menu.add_command(label="退出", command=self._on_close)
        
        # 查看菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="查看", menu=view_menu)
        view_menu.add_command(label="刷新数据", command=self._refresh_data)
        view_menu.add_command(label="清空日志", command=self._clear_log)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)
        
    def _create_main_layout(self):
        """创建主布局"""
        # 主框架
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部状态栏
        self._create_header(main_frame)
        
        # 中间内容区（左右分栏）
        content_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        content_frame.grid_columnconfigure(0, weight=3)
        content_frame.grid_columnconfigure(1, weight=2)
        
        # 左侧面板
        left_panel = tk.Frame(content_frame, bg=self.colors['bg'])
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._create_left_panel(left_panel)
        
        # 右侧面板
        right_panel = tk.Frame(content_frame, bg=self.colors['bg'])
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._create_right_panel(right_panel)
        
        # 底部日志区
        self._create_log_panel(main_frame)
        
    def _create_header(self, parent):
        """创建顶部状态栏 - 只显示当日盈亏，去掉总资产"""
        header = tk.Frame(parent, bg=self.colors['bg_secondary'], 
                         highlightbackground=self.colors['border'], 
                         highlightthickness=1)
        header.pack(fill=tk.X, pady=(0, 10))
        
        # 系统状态
        self.status_label = tk.Label(header, text="⏹ 已停止", 
                                    font=("Microsoft YaHei", 14, "bold"),
                                    bg=self.colors['bg_secondary'],
                                    fg=self.colors['text'])
        self.status_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 时间显示
        self.time_label = tk.Label(header, text="--:--:--",
                                  font=("Microsoft YaHei", 12),
                                  bg=self.colors['bg_secondary'],
                                  fg=self.colors['text_secondary'])
        self.time_label.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # 资金信息 - 只显示当日盈亏
        self.capital_frame = tk.Frame(header, bg=self.colors['bg_secondary'])
        self.capital_frame.pack(side=tk.RIGHT, padx=20)
        
        tk.Label(self.capital_frame, text="  当日盈亏: ", 
                font=("Microsoft YaHei", 11),
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary']).pack(side=tk.LEFT)
        
        self.pnl_label = tk.Label(self.capital_frame, text="+0.00 (0.00%)",
                                 font=("Microsoft YaHei", 11, "bold"),
                                 bg=self.colors['bg_secondary'],
                                 fg=self.colors['text'])
        self.pnl_label.pack(side=tk.LEFT)
        
    def _create_left_panel(self, parent):
        """创建左侧面板（持仓和信号）"""
        # 持仓表格
        positions_frame = tk.LabelFrame(parent, text="📊 持仓监控", 
                                       font=("Microsoft YaHei", 11, "bold"),
                                       bg=self.colors['bg_secondary'],
                                       fg=self.colors['text'],
                                       highlightbackground=self.colors['border'],
                                       highlightthickness=1)
        positions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 创建表格
        columns = ('代码', '名称', '持仓', '成本', '现价', '盈亏', '盈亏率')
        self.positions_tree = ttk.Treeview(positions_frame, columns=columns, 
                                          show='headings', height=8)
        
        for col in columns:
            self.positions_tree.heading(col, text=col)
            self.positions_tree.column(col, width=80, anchor='center')
        
        # 滚动条
        scrollbar = ttk.Scrollbar(positions_frame, orient=tk.VERTICAL, 
                                 command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # 信号表格
        signals_frame = tk.LabelFrame(parent, text="🔔 交易信号", 
                                     font=("Microsoft YaHei", 11, "bold"),
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text'],
                                     highlightbackground=self.colors['border'],
                                     highlightthickness=1)
        signals_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # 持仓表只显示仓位提醒，信号表独立显示
        columns2 = ('时间', '代码', '动作', '价格', '原因')
        self.signals_tree = ttk.Treeview(signals_frame, columns=columns2, 
                                        show='headings', height=4)
        
        for col in columns2:
            self.signals_tree.heading(col, text=col)
            width = 200 if col == '原因' else 80
            self.signals_tree.column(col, width=width, anchor='center')
        
        scrollbar2 = ttk.Scrollbar(signals_frame, orient=tk.VERTICAL, 
                                  command=self.signals_tree.yview)
        self.signals_tree.configure(yscrollcommand=scrollbar2.set)
        
        self.signals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
    def _create_right_panel(self, parent):
        """创建右侧面板（风险和交易记录）"""
        # 风险指标
        risk_frame = tk.LabelFrame(parent, text="⚠️ 风险指标", 
                                  font=("Microsoft YaHei", 11, "bold"),
                                  bg=self.colors['bg_secondary'],
                                  fg=self.colors['text'],
                                  highlightbackground=self.colors['border'],
                                  highlightthickness=1)
        risk_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.risk_labels = {}
        risk_items = [
            ('var_95', 'VaR (95%):', '--'),
            ('max_drawdown', '最大回撤:', '--'),
            ('daily_limit', '日限额:', '--'),
            ('position_ratio', '仓位比例:', '--'),
        ]
        
        for key, label, value in risk_items:
            row = tk.Frame(risk_frame, bg=self.colors['bg_secondary'])
            row.pack(fill=tk.X, padx=10, pady=3)
            
            tk.Label(row, text=label, 
                    font=("Microsoft YaHei", 10),
                    bg=self.colors['bg_secondary'],
                    fg=self.colors['text_secondary']).pack(side=tk.LEFT)
            
            self.risk_labels[key] = tk.Label(row, text=value,
                                            font=("Microsoft YaHei", 10, "bold"),
                                            bg=self.colors['bg_secondary'],
                                            fg=self.colors['text'])
            self.risk_labels[key].pack(side=tk.RIGHT)
        
        # 交易记录
        trades_frame = tk.LabelFrame(parent, text="📈 最近交易", 
                                    font=("Microsoft YaHei", 11, "bold"),
                                    bg=self.colors['bg_secondary'],
                                    fg=self.colors['text'],
                                    highlightbackground=self.colors['border'],
                                    highlightthickness=1)
        trades_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.trades_text = scrolledtext.ScrolledText(
            trades_frame, 
            font=("Consolas", 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            height=12
        )
        self.trades_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.trades_text.insert(tk.END, "暂无交易记录\n")
        self.trades_text.config(state=tk.DISABLED)
        
    def _create_log_panel(self, parent):
        """创建日志面板"""
        log_frame = tk.LabelFrame(parent, text="📝 系统日志", 
                                 font=("Microsoft YaHei", 11, "bold"),
                                 bg=self.colors['bg_secondary'],
                                 fg=self.colors['text'],
                                 highlightbackground=self.colors['border'],
                                 highlightthickness=1)
        log_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            bg=self.colors['bg'],
            fg=self.colors['text_secondary'],
            insertbackground=self.colors['text'],
            height=6
        )
        self.log_text.pack(fill=tk.X, padx=5, pady=5)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] 系统初始化完成\n")
        self.log_text.config(state=tk.DISABLED)
        
    def _create_status_bar(self):
        """创建底部状态栏"""
        status_bar = tk.Frame(self.root, bg=self.colors['accent'], height=25)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_text = tk.Label(status_bar, 
                                   text="就绪 | 按F5刷新 | 交易时间: 09:30-11:30, 13:00-15:00",
                                   font=("Microsoft YaHei", 9),
                                   bg=self.colors['accent'],
                                   fg=self.colors['text_secondary'])
        self.status_text.pack(side=tk.LEFT, padx=10)
        
    def _auto_refresh(self):
        """自动刷新数据线程"""
        while self.running:
            try:
                self.root.after(0, self._update_time)
                if self.trading_system:
                    self.root.after(0, self._update_data)
                time.sleep(1)
            except Exception as e:
                time.sleep(1)
                
    def _update_time(self):
        """更新时间显示"""
        current = datetime.now().strftime('%H:%M:%S')
        self.time_label.config(text=current)
        
    def _update_data(self):
        """更新界面数据"""
        if not self.trading_system:
            return
            
        try:
            state = self.trading_system.get_system_state()
            
            # 更新状态
            status = state.get('status', 'unknown')
            if status == 'running':
                self.status_label.config(text="▶ 运行中", fg=self.colors['down'])
            else:
                self.status_label.config(text="⏹ 已停止", fg=self.colors['text'])
                
            # 更新当日盈亏（去掉总资产）
            daily_pnl = state.get('daily_pnl', 0)
            daily_pnl_pct = state.get('daily_pnl_pct', 0)
            
            pnl_color = self.colors['up'] if daily_pnl >= 0 else self.colors['down']
            pnl_sign = '+' if daily_pnl >= 0 else ''
            self.pnl_label.config(
                text=f"{pnl_sign}{daily_pnl:,.2f} ({daily_pnl_pct:+.2f}%)",
                fg=pnl_color
            )
            
            # 更新持仓表格
            self._update_positions(state.get('positions', {}))
            
            # 更新信号表格
            self._update_signals(state.get('signals', []))
            
            # 更新风险指标
            risk = state.get('risk', {})
            self._update_risk(risk)
            
            # 更新交易记录
            self._update_trades(state.get('trades', []))
            
        except Exception as e:
            self._log(f"更新数据失败: {e}")
            
    def _update_positions(self, positions):
        """更新持仓表格"""
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        if not positions:
            self.positions_tree.insert('', tk.END, values=(
                "--", "没有符合条件的股票", "--", "--", "--", "--", "--"
            ))
            return
            
        for code, pos in positions.items():
            shares = pos.get('shares', 0)
            cost = pos.get('entry_price', pos.get('avg_cost', 0))
            current = pos.get('current_price', pos.get('current_price', cost))
            name = pos.get('name', code)
            pnl = pos.get('pnl', 0)
            pnl_pct = pos.get('pnl_pct', 0)
            
            # 如果没有pnl，手动计算
            if pnl == 0 and current > 0 and cost > 0:
                pnl = (current - cost) * shares
                pnl_pct = ((current / cost) - 1) * 100
            
            self.positions_tree.insert('', tk.END, values=(
                code,
                name,
                f"{shares:,}",
                f"¥{cost:.2f}",
                f"¥{current:.2f}" if current else "--",
                f"¥{pnl:,.2f}" if pnl else "--",
                f"{pnl_pct:+.2f}%" if pnl_pct else "--"
            ))
            
    def _update_signals(self, signals):
        """更新信号表格 - 持仓表只做仓位提醒，信号独立"""
        for item in self.signals_tree.get_children():
            self.signals_tree.delete(item)
        
        if not signals:
            self.signals_tree.insert('', tk.END, values=(
                "--", "--", "暂无交易信号", "--", "--"
            ))
            return
            
        for signal in signals[-10:]:
            action = signal.get('action', '--')
            self.signals_tree.insert('', 0, values=(
                signal.get('time', '--'),
                signal.get('code', '--'),
                action,
                f"¥{signal.get('price', 0):.2f}",
                signal.get('reason', '--')[:30]
            ))
            
    def _update_risk(self, risk):
        """更新风险指标"""
        var_val = risk.get('var_95', 0) or risk.get('var', {}).get('var_95', 0)
        if isinstance(var_val, dict):
            var_val = var_val.get('value', 0)
        
        self.risk_labels['var_95'].config(
            text=f"¥{float(var_val or 0):,.2f}"
        )
        
        dd = risk.get('max_drawdown_pct', 0) or 0
        self.risk_labels['max_drawdown'].config(
            text=f"{float(dd):.2f}%"
        )
        
        dl = risk.get('daily_limit_used', 0) or risk.get('daily_pnl_pct', 0) or 0
        self.risk_labels['daily_limit'].config(
            text=f"{float(dl):.1f}%"
        )
        
        pr = risk.get('position_ratio', 0) or 0
        self.risk_labels['position_ratio'].config(
            text=f"{float(pr):.1f}%"
        )
        
    def _update_trades(self, trades):
        """更新交易记录 - 买红色，卖绿色"""
        self.trades_text.config(state=tk.NORMAL)
        self.trades_text.delete(1.0, tk.END)
        
        if not trades:
            self.trades_text.insert(tk.END, "暂无交易记录\n")
        else:
            for trade in trades:
                time_str = trade.get('time', '--')
                code = trade.get('code', '--')
                action = trade.get('action', '--')
                price = trade.get('price', 0)
                shares = trade.get('shares', 0)
                pnl = trade.get('pnl', 0)
                pnl_str = f" 盈亏: ¥{pnl:,.2f}" if pnl != 0 else ""
                
                # 买红卖绿，动作显示中文
                if action.upper() in ('BUY', '买入'):
                    action_cn = "买"
                    color = self.colors['up']   # 红色
                else:
                    action_cn = "卖"
                    color = self.colors['down']  # 绿色
                
                line = f"{time_str} | {code} | {action_cn} | {shares}股 @ ¥{price:.2f}{pnl_str}\n"
                
                # 先插入文字
                end_idx = self.trades_text.index(tk.END)
                self.trades_text.insert(tk.END, line)
                
                # 再上色（整行）
                start_idx = f"{float(end_idx) - 1:.1f}.0"
                self.trades_text.tag_add(f"trade_{time_str}", start_idx, end_idx)
                self.trades_text.tag_config(f"trade_{time_str}", foreground=color)
                
        self.trades_text.config(state=tk.DISABLED)
        
    def _log(self, message):
        """添加日志"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def _refresh_data(self):
        """手动刷新数据"""
        self._update_data()
        self._log("手动刷新完成")
        
    def _clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def _start_trading(self):
        """启动交易（手动触发一次扫描）"""
        self._log("手动触发扫描...")
        if self.trading_system:
            # 在后台线程执行扫描
            def do_scan():
                try:
                    self.trading_system.scan_and_trade()
                    self.root.after(0, lambda: self._log(f"扫描完成 | 共 {self.trading_system.scan_count} 轮"))
                    self.root.after(0, self._refresh_data)
                except Exception as e:
                    self.root.after(0, lambda e=e: self._log(f"扫描异常: {e}"))
            threading.Thread(target=do_scan, daemon=True).start()
        
    def _stop_trading(self):
        """停止交易"""
        if self.trading_system:
            self.trading_system.running = False
            self._log("交易循环已停止")
            self.status_label.config(text="⏹ 已停止", fg=self.colors['text'])
        
    def _show_about(self):
        """显示关于对话框"""
        about = tk.Toplevel(self.root)
        about.title("关于 AutoTrader V3")
        about.geometry("300x150")
        about.resizable(False, False)
        about.transient(self.root)
        
        tk.Label(about, text="AutoTrader V3", 
                font=("Microsoft YaHei", 16, "bold")).pack(pady=10)
        tk.Label(about, text="A股做T量化交易系统", 
                font=("Microsoft YaHei", 11)).pack()
        tk.Label(about, text="版本: 3.1.2", 
                font=("Microsoft YaHei", 9)).pack(pady=5)
        
        tk.Button(about, text="确定", command=about.destroy,
                 width=10).pack(pady=10)
        
    def _manage_positions(self):
        """管理持仓对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("持仓管理")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        list_frame = tk.Frame(dialog, padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(list_frame, text="当前持仓:", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W)
        
        self.pos_listbox = tk.Listbox(list_frame, height=8, font=("Microsoft YaHei", 10))
        self.pos_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self._refresh_position_list()
        
        btn_frame = tk.Frame(dialog, padx=10, pady=5)
        btn_frame.pack(fill=tk.X)
        
        tk.Button(btn_frame, text="添加持仓", command=lambda: self._add_position_dialog(dialog),
                 width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="删除选中", command=lambda: self._delete_position(dialog),
                 width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="保存到文件", command=self._save_positions,
                 width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="关闭", command=dialog.destroy,
                 width=10).pack(side=tk.RIGHT, padx=5)
        
    def _refresh_position_list(self):
        """刷新持仓列表"""
        self.pos_listbox.delete(0, tk.END)
        
        if self.trading_system:
            # 从 risk_manager.position_mgr 读取底仓信息
            pm = self.trading_system.risk_manager.position_mgr
            for code, pos in pm.get_all_positions().items():
                name = pos.get('name', code)
                shares = pos.get('shares', 0)
                cost = pos.get('entry_price', 0)
                if shares > 0:
                    self.pos_listbox.insert(tk.END, f"{code} | {name} | {shares}股 | 成本¥{cost}")
        
        if self.pos_listbox.size() == 0:
            self.pos_listbox.insert(tk.END, "002539 | 云图控股 | 14900股 | 成本¥10.625")
            
    def _add_position_dialog(self, parent):
        """添加持仓对话框"""
        dialog = tk.Toplevel(parent)
        dialog.title("添加持仓")
        dialog.geometry("300x250")
        dialog.transient(parent)
        dialog.grab_set()
        
        tk.Label(dialog, text="股票代码:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=10, pady=(10,0))
        code_entry = tk.Entry(dialog, font=("Microsoft YaHei", 10))
        code_entry.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(dialog, text="股票名称:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=10, pady=(10,0))
        name_entry = tk.Entry(dialog, font=("Microsoft YaHei", 10))
        name_entry.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(dialog, text="持仓数量:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=10, pady=(10,0))
        shares_entry = tk.Entry(dialog, font=("Microsoft YaHei", 10))
        shares_entry.pack(fill=tk.X, padx=10, pady=2)
        shares_entry.insert(0, "0")
        
        tk.Label(dialog, text="成本价:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=10, pady=(10,0))
        cost_entry = tk.Entry(dialog, font=("Microsoft YaHei", 10))
        cost_entry.pack(fill=tk.X, padx=10, pady=2)
        cost_entry.insert(0, "0.0")
        
        def do_add():
            code = code_entry.get().strip()
            name = name_entry.get().strip() or code
            try:
                shares = int(shares_entry.get())
                cost = float(cost_entry.get())
            except ValueError:
                tk.messagebox.showerror("错误", "持仓数量和成本价必须是数字")
                return
            if not code:
                tk.messagebox.showerror("错误", "股票代码不能为空")
                return
            
            if self.trading_system:
                pm = self.trading_system.risk_manager.position_mgr
                pm._positions[code] = {
                    "code": code,
                    "entry_price": cost,
                    "shares": shares,
                    "action": "BUY",
                    "entry_time": datetime.now(),
                    "stop_loss": cost * 0.95,
                    "take_profit": cost * 1.05,
                    "highest_price": cost,
                    "lowest_price": cost,
                    "pnl": 0.0,
                    "pnl_pct": 0.0,
                    "name": name,
                    "is_base_position": True,
                }
            
            self._log(f"添加持仓: {code} {name} {shares}股 @ ¥{cost}")
            self._refresh_position_list()
            dialog.destroy()
            
        tk.Button(dialog, text="确定", command=do_add, width=10).pack(pady=15)
        
    def _delete_position(self, parent):
        """删除选中持仓"""
        selection = self.pos_listbox.curselection()
        if not selection:
            tk.messagebox.showwarning("提示", "请先选择要删除的持仓")
            return
            
        item = self.pos_listbox.get(selection[0])
        code = item.split(" | ")[0]
        
        if tk.messagebox.askyesno("确认", f"确定删除持仓 {code} 吗?"):
            if self.trading_system:
                pm = self.trading_system.risk_manager.position_mgr
                if code in pm._positions:
                    del pm._positions[code]
                    self._log(f"删除持仓: {code}")
            self._refresh_position_list()
            
    def _save_positions(self):
        """保存持仓到文件"""
        try:
            import json
            from pathlib import Path
            
            save_path = Path.home() / "Documents" / "auto_trader_v3" / "positions.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            positions = {}
            if self.trading_system:
                for code, pos in self.trading_system.risk_manager.position_mgr.get_all_positions().items():
                    positions[code] = {
                        "name": pos.get("name", code),
                        "base_shares": pos.get("shares", 0),
                        "base_cost": pos.get("entry_price", 0),
                    }
            else:
                positions = {
                    "002539": {
                        "name": "云图控股",
                        "base_shares": 14900,
                        "base_cost": 10.625,
                    }
                }
                
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(positions, f, ensure_ascii=False, indent=2)
                
            self._log(f"持仓已保存到: {save_path}")
            tk.messagebox.showinfo("成功", f"持仓已保存到:\n{save_path}")
        except Exception as e:
            self._log(f"保存持仓失败: {e}")
            tk.messagebox.showerror("错误", f"保存失败: {e}")
        
    def _on_close(self):
        """关闭窗口"""
        self.running = False
        self.root.quit()
        self.root.destroy()
        
    def run(self):
        """启动GUI主循环"""
        # 启动后延迟3秒自动刷新一次数据（等交易系统初始化完成）
        self.root.after(3000, self._on_startup_refresh)
        self.root.mainloop()
        
    def _on_startup_refresh(self):
        """GUI启动后自动刷新一次数据并触发扫描"""
        self._log("系统就绪，正在获取数据...")
        self._refresh_data()
        # 自动触发一次扫描
        if self.trading_system:
            self._start_trading()


def run_gui(trading_system=None):
    """启动GUI的便捷函数"""
    gui = TradingGUI(trading_system)
    gui.run()


if __name__ == "__main__":
    run_gui()
