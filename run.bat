@echo off
title UniScholar WebUI
echo ========================================================
echo   UniScholar (联智学者) - 通用AI科研智能体应用系统
echo   Address: http://127.0.0.1:7860
echo ========================================================

REM 优先尝试当前用户目录下的 Python 3.10 绝对路径与启动器
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" app.py
    goto :done
)

py -3.10 --version >nul 2>nul
if %errorlevel%==0 (
    py -3.10 app.py
    goto :done
)

python --version >nul 2>nul
if %errorlevel%==0 (
    python app.py
    goto :done
)

echo [Error] Python 3.10+ not found. Please ensure Python is installed.

:done
pause
