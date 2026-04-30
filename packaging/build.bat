@echo off
REM AutoTrader v3.0 Windows打包脚本
REM 使用: 在项目根目录运行 build.bat

echo ========================================
echo AutoTrader v3.0 Windows EXE 打包
echo ========================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

REM 检查依赖
echo [1/4] 检查依赖...
pip install -r requirements_windows.txt -q
if errorlevel 1 (
    echo [警告] 依赖安装失败，尝试继续...
)

REM 清理旧构建
echo [2/4] 清理旧构建...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "*.spec" if not exist "packaging\*.spec" copy *.spec dist\ 2>nul

REM PyInstaller打包
echo [3/4] PyInstaller打包中...
pyinstaller packaging\auto_trader.spec --clean
if errorlevel 1 (
    echo [错误] PyInstaller打包失败
    pause
    exit /b 1
)

REM 完成
echo [4/4] 打包完成!
echo.
echo EXE位置: dist\auto_trader_v3\auto_trader_v3.exe
echo.
echo 启动测试:
echo   dist\auto_trader_v3\auto_trader_v3.exe --scan
echo   dist\auto_trader_v3\auto_trader_v3.exe --dashboard
echo.
pause
