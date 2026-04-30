# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller打包配置
构建命令: pyinstaller auto_trader.spec
"""
import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 配置文件
        ('config', 'config'),
        ('stock_pool.json', '.'),
    ],
    hiddenimports=[
        # AkShare子模块
        'akshare',
        'akshare.stock',
        'akshare.stock.stock_zh_a_spot_em',
        'akshare.stock.stock_zh_a_hist',
        # 数据处理
        'pandas',
        'numpy',
        'requests',
        # HTTP服务器
        'http.server',
        'urllib.request',
    ],
    hookspath=[],
    hooksconfig={},
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='auto_trader_v3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # 可选: 添加应用图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='auto_trader_v3',
)
