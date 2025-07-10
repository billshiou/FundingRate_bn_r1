@echo off
title 资金费率套利机器人
cls

echo ========================================
echo      资金费率套利机器人 v2.0
echo ========================================
echo.
echo 🚀 正在启动机器人...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未检测到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

REM 检查配置文件
if not exist config.py (
    echo ❌ 错误：config.py配置文件不存在
    echo 💡 请先复制 config_example.py 为 config.py 并填入你的API密钥
    pause
    exit /b 1
)

echo ✅ Python环境检查通过
echo ✅ 配置文件检查通过
echo.
echo 🔄 正在启动交易机器人...
echo.

REM 启动主程序
python test_trading_minute.py

REM 如果程序异常退出，显示错误信息
if %errorlevel% neq 0 (
    echo.
    echo ❌ 程序异常退出，错误代码: %errorlevel%
    echo 💡 请检查配置文件和网络连接
)

echo.
echo 👋 程序已退出，按任意键关闭窗口...
pause >nul 