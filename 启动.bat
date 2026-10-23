@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "VENV=%~dp0.venv"

if not exist "%VENV%\python.exe" (
    echo.
    echo [错误] 找不到虚拟环境：%VENV%\python.exe
    echo.
    echo 请先创建并安装依赖，详见 使用方法.md：
    echo     conda create -p .venv python=3.10 gdspy=1.6.13 pip
    echo     .venv\python.exe -m pip install -r requirements.txt
    echo     .venv\python.exe -m pip install dgl==1.1.2
    echo.
    pause
    exit /b 1
)

echo 正在启动 模拟电路自动化设计工具 (Parms) ...
"%VENV%\python.exe" "%~dp0main_ui.py"

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误码 %errorlevel%
    echo 常见原因：
    echo   - 依赖没装全  ^(pip install -r requirements.txt^)
    echo   - 没在仓库根目录启动  ^(本脚本已自动 cd 到脚本所在目录^)
    echo.
    pause
)
