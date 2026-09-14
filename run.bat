@chcp 65001 >nul
@echo off
title UniScholar (联智学者) WebUI
setlocal enabledelayedexpansion

REM 启用 Python 全局 UTF-8 编码模式，彻底杜绝控制台乱码
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================================
echo   UniScholar (联智学者) - 通用AI科研智能体应用系统
echo   服务地址: http://127.0.0.1:7860
echo ========================================================
echo.
echo 正在检查 Python 3.10+ 环境...

REM 1. 优先使用 Python 启动器 py -3.10
py -3.10 --version >nul 2>nul
if %errorlevel%==0 (
    echo [OK] 检测到 Python 启动器 (py -3.10)
    echo 正在启动 WebUI 服务...
    py -3.10 app.py
    goto :done
)

REM 2. 尝试用户本地安装目录下的 Python 3.10
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    echo [OK] 检测到本地 Python 3.10 解释器
    echo 正在启动 WebUI 服务...
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" app.py
    goto :done
)

REM 3. 尝试全局环境变量中的 python
python --version >nul 2>nul
if %errorlevel%==0 (
    echo [OK] 检测到全局 python
    echo 正在启动 WebUI 服务...
    python app.py
    goto :done
)

echo.
echo [错误] 未检测到 Python 3.10+ 环境，请确保已安装 Python 并加入系统环境变量 PATH。
echo.

:done
if %errorlevel% neq 0 (
    echo.
    echo [提示] 程序已退出 (退出码: %errorlevel%)
)
pause
