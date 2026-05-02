# -*- mode: python ; coding: utf-8 -*-
import os
import glob

block_cipher = None

# 收集 akshare 的数据文件（csv/json等）
akshare_datas = []
try:
    import akshare
    akshare_dir = os.path.dirname(akshare.__file__)
    # 收集所有非 .pyc / __pycache__ 的数据文件
    for root, dirs, files in os.walk(akshare_dir):
        for f in files:
            if f.endswith(('.pyc', '.pyo')):
                continue
            # 跳过 __pycache__ 目录
            if '__pycache__' in root:
                continue
            src = os.path.join(root, f)
            dst = os.path.relpath(root, os.path.dirname(akshare_dir))
            akshare_datas.append((src, dst))
except Exception:
    pass

# 收集项目内所有 Python 包
project_datas = []
for root, dirs, files in os.walk('.'):
    # 跳过不需要的目录
    skip = {'__pycache__', '.git', '.github', 'test_logs', 'logs',
            'trading_signals', 'node_modules', '.pytest_cache', 'dist', 'build'}
    dirs[:] = [d for d in dirs if d not in skip]
    for f in files:
        if f.endswith(('.py', '.json', '.csv', '.txt', '.cfg', '.ini', '.yaml', '.yml')):
            src = os.path.join(root, f)
            dst = root if root != '.' else ''
            project_datas.append((src, dst))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=akshare_datas + project_datas,
    hiddenimports=[
        # 项目模块
        'config.settings',
        'config.risk_params',
        'config.strategy_params',
        'data.datasource',
        'data.cache',
        'data.validator',
        'strategy.engine',
        'strategy.bayesian_fusion',
        'strategy.indicators',
        'strategy.factors.base',
        'strategy.factors.momentum',
        'strategy.factors.volatility',
        'strategy.factors.volume',
        'strategy.factors.microstructure',
        'strategy.multi_timeframe',
        'risk.kelly',
        'risk.var',
        'risk.position',
        'risk.limits',
        'risk.manager',
        'execution.order_manager',
        'execution.executor',
        'execution.file_signal',
        'execution.ths_trades_adapter',
        'backtest.engine',
        'backtest.t1_constraint',
        'backtest.cost_model',
        'backtest.performance',
        'backtest.data_loader',
        'monitor.alerts',
        'monitor.logger',
        'monitor.web_dashboard',
        # 第三方依赖
        'numpy',
        'akshare',
        'pandas',
        'pandas._libs',
        'pandas._libs.tslibs',
        'pandas.core.arrays.masked',
        'pandas.core.computation.expressions',
        'pyarrow',
        'pyarrow.pandas_compat',
        'lxml',
        'lxml._elementpath',
        'lxml.etree',
        'html5lib',
        'bs4',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'tqdm',
        'decorator',
        'logging',
        'multiprocessing',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='auto_trader_v3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesigning_identity=None,
    entitlements_file=None,
    icon=None,
)
