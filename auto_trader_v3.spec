# ============================================================
# AutoTrader v3.0 — PyInstaller 打包配置 (v3修复版)
# 修复: __file__未定义 / DEST_DIR必须相对路径
# ============================================================
import os
import sys
import glob
from pathlib import Path

block_cipher = None

# PyInstaller执行spec时__file__未定义，用SPECPATH
# SPECPATH = spec文件所在目录（即项目根目录，因为spec和main.py同目录）
project_root = Path(SPECPATH)

# ---- 数据文件（必须用相对路径） ----
project_datas = []

# stock_pool.json 是运行时必需的
stock_pool = project_root / 'stock_pool.json'
if stock_pool.exists():
    project_datas.append((str(stock_pool), '.'))

# akshare 数据文件（交易日历、JS、ZIP等）
try:
    import akshare
    akshare_dir = Path(akshare.__file__).parent
    # 收集所有非Python数据文件
    data_exts = {'.json', '.js', '.zip', '.csv', '.txt', '.xml', '.html'}
    for data_file in akshare_dir.rglob('*'):
        if data_file.is_file() and data_file.suffix.lower() in data_exts:
            rel_path = data_file.parent.relative_to(akshare_dir)
            dest_dir = str(Path('akshare') / rel_path)
            project_datas.append((str(data_file), dest_dir))
except Exception as e:
    print(f"警告: 无法收集akshare数据文件: {e}")

# requirements文件（信息用途）
for f in ['requirements.txt', 'requirements_windows.txt']:
    fp = project_root / f
    if fp.exists():
        project_datas.append((str(fp), '.'))

# ---- 隐藏导入 ----
hidden_imports = [
    # 项目模块
    'config', 'config.settings', 'config.risk_params', 'config.strategy_params',
    'data', 'data.datasource', 'data.cache', 'data.validator',
    'data.akshare_adapter', 'data.sina_adapter', 'data.tencent_adapter',
    'strategy', 'strategy.engine', 'strategy.bayesian_fusion',
    'strategy.indicators', 'strategy.signals', 'strategy.multi_timeframe',
    'strategy.factors', 'strategy.factors.base',
    'strategy.factors.momentum', 'strategy.factors.volatility',
    'strategy.factors.volume', 'strategy.factors.microstructure',
    'risk', 'risk.kelly', 'risk.var', 'risk.position', 'risk.limits', 'risk.manager',
    'execution', 'execution.order_manager', 'execution.executor',
    'execution.file_signal', 'execution.ths_trades_adapter',
    'backtest', 'backtest.engine', 'backtest.t1_constraint',
    'backtest.cost_model', 'backtest.performance', 'backtest.data_loader',
    'monitor', 'monitor.alerts', 'monitor.logger', 'monitor.web_dashboard',
    # 第三方依赖
    'numpy', 'numpy.core', 'numpy.core.multiarray', 'numpy.linalg',
    'pandas', 'pandas._libs', 'pandas._libs.tslibs',
    'pandas._libs.hashtable', 'pandas._libs.lib',
    'pandas.core', 'pandas.core.arrays', 'pandas.core.computation',
    'lxml', 'lxml._elementpath', 'lxml.etree',
    'html5lib', 'html5lib.treewalkers', 'html5lib.treewalkers.lxml',
    'bs4', 'requests', 'urllib3', 'certifi', 'charset_normalizer',
    'idna', 'tqdm', 'decorator', 'packaging', 'pkg_resources',
    'dateutil', 'six', 'typing_extensions', 'pytz',
    # 编码
    'encodings', 'encodings.utf_8', 'encodings.gbk', 'encodings.cp936',
    # 并发
    'multiprocessing', 'threading', 'concurrent.futures',
    # akshare依赖链
    'akshare', 'jsonpath', 'mini_racer', 'curl_cffi',
    'openpyxl', 'xlrd',
]

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=project_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'PIL', 'Pillow',
        'IPython', 'jupyter', 'notebook', 'pytest', 'cv2',
        'torch', 'tensorflow', 'keras', 'sympy', 'nbconvert',
        'notebook', 'IPython', 'jupyter_client', 'jupyter_core',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesigning_identity=None,
    entitlements_file=None,
    icon=None,
)
