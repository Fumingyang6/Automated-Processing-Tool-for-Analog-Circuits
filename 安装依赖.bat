@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Parms 依赖安装（Python 3.10 + gdspy）
echo ============================================
echo.

where conda >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有检测到 conda。
    echo 请先安装 Miniconda：
    echo     https://docs.conda.io/en/latest/miniconda.html
    echo 安装完成后重新打开命令行，再双击本脚本。
    echo.
    pause
    exit /b 1
)

if not exist ".venv\python.exe" (
    echo [1/3] 创建虚拟环境 .venv ...
    call conda create -y -p .venv --override-channels -c conda-forge python=3.10 gdspy=1.6.13 pip
    if errorlevel 1 (
        echo.
        echo [错误] 创建环境失败，请把上面的报错发给维护者。
        pause
        exit /b 1
    )
) else (
    echo [1/3] 已存在 .venv，跳过创建。
)

echo.
echo [2/3] 安装 Python 依赖（首次安装 torch 等包会比较久）...
".venv\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请把上面的报错发给维护者。
    pause
    exit /b 1
)

echo.
echo [3/3] 检查关键依赖 ...
".venv\python.exe" -c "import PyQt5, numpy, scipy, matplotlib, networkx, torch, dgl, torch_geometric, gdspy; print('依赖检查通过')"
if errorlevel 1 (
    echo.
    echo [错误] 关键依赖导入失败。
    pause
    exit /b 1
)

echo.
echo 安装完成。以后双击 启动.bat 即可运行程序。
pause
