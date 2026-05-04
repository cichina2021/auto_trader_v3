# ============================================================
# AutoTrader v3.0 — PyInstaller 打包配置 (修复版)
# 支持 Windows 便携版一键打包
# ============================================================
import os
import sys
import glob
from pathlib import Path

block_cipher = None

# ---- 收集 akshare 数据文件 ----
akshare_datas = []
try:
    import akshare
    akshare_dir = os.path.dirname(akshare.__file__)
    for root, dirs, files in os.walk(akshare_dir):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.pytest_cache'}]
        for f in files:
            if f.endswith(('.pyc', '.pyo')):
                continue
            src = os.path.join(root, f)
            # 放到 akshare/ 子目录
            rel = os.path.relpath(root, os.path.dirname(akshare_dir))
            akshare_datas.append((src, rel))
except Exception:
    pass

# ---- 收集项目所有 Python 包和配置文件 ----
project_datas = []
project_root = Path(__file__).parent.parent

skip_dirs = {
    '__pycache__', '.git', '.github', 'test_logs', 'logs',
    'trading_signals', 'node_modules', '.pytest_cache',
    'dist', 'build', '.archive', '__pyautotrader__'
}

for root, dirs, files in os.walk(project_root):
    # 跳过不需要的目录
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for f in files:
        if f.endswith(('.pyc', '.pyo')):
            continue
        if f in ('.DS_Store', 'Thumbs.db'):
            continue
        src = os.path.join(root, f)
        rel = root if root != str(project_root) else '.'
        # 所有配置和数据文件都打包
        if f.endswith(('.py', '.json', '.csv', '.txt', '.cfg', '.ini', '.yaml', '.yml', '.md')):
            project_datas.append((src, rel))

# ---- 隐藏导入（必须确保PyInstaller能找到所有模块）----
hidden_imports = [
    # 项目模块
    'config.settings',
    'config.risk_params',
    'config.strategy_params',
    'data.datasource',
    'data.cache',
    'data.validator',
    'data.akshare_adapter',
    'data.sina_adapter',
    'data.tencent_adapter',
    'strategy.engine',
    'strategy.bayesian_fusion',
    'strategy.indicators',
    'strategy.signals',
    'strategy.multi_timeframe',
    'strategy.factors.base',
    'strategy.factors.momentum',
    'strategy.factors.volatility',
    'strategy.factors.volume',
    'strategy.factors.microstructure',
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
    # 第三方依赖（PyInstaller可能漏掉的）
    'numpy',
    'numpy.core',
    'numpy.core.multiarray',
    'numpy.linalg',
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'pandas._libs.hashtable',
    'pandas._libs.lib',
    'pandas.core',
    'pandas.core.arrays',
    'pandas.core.computation',
    'pyarrow',
    'pyarrow._ parquet',
    'lxml',
    'lxml._elementpath',
    'lxml.etree',
    'html5lib',
    'html5lib.treewalkers',
    'html5lib.treewalkers.lxml',
    'bs4',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    'tqdm',
    'decorator',
    'packaging',
    'pkg_resources',
    'logging',
    'multiprocessing',
    'threading',
    'concurrent.futures',
    'encodings',
    'encodings.utf_8',
    'dateutil',
    'six',
    'typing_extensions',
    'pytz',
    'etzire',
    # 执行层入口
    'execution',
    'execution.__init__',
]

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[],
    binaries=[],
    datas=akshare_datas + project_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'PIL',
        'Pillow',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'cv2',
        'torch',
        'tensorflow',
        'keras',
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
    name='AutoTraderV3',
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