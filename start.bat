@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM P01_fapiao_helper 启动脚本（Windows）
REM 双击运行：自动准备 venv、安装依赖、启动服务并打开浏览器到 http://127.0.0.1:5000
cd /d "%~dp0"

set VENV=.venv
set PYTHON=%VENV%\Scripts\python.exe
set PIP=%VENV%\Scripts\pip.exe
set REQ=requirements.txt
set URL=http://127.0.0.1:5000
set MARKER=%VENV%\.deps_installed

REM 1. 创建虚拟环境
if not exist "%PYTHON%" (
    echo [1/4] 创建虚拟环境 .venv ...
    python -m venv %VENV%
    if errorlevel 1 (
        echo 创建虚拟环境失败，请确认已安装 Python 3.9+ 并加入 PATH。
        pause
        exit /b 1
    )
)

REM 2. 安装依赖（首次或 requirements.txt 更新时）
REM 检查 requirements.txt 是否比 marker 新（与 start.sh 行为一致）
if exist "%MARKER%" (
    set "NEWEST="
    for /f "delims=" %%i in ('dir /b /o-d "%REQ%" "%MARKER%" 2^>nul') do (
        if "!NEWEST!"=="" set "NEWEST=%%i"
    )
    if "!NEWEST!"=="%REQ%" (
        echo 检测到 requirements.txt 已更新，重新安装依赖...
        del "%MARKER%"
    )
)
if not exist "%MARKER%" (
    echo [2/4] 安装依赖（首次较慢，含 PaddleOCR 模型约 200MB）...
    %PIP% install --upgrade pip
    %PIP% install -r %REQ%
    if errorlevel 1 (
        echo 依赖安装失败，请检查网络或 requirements.txt。
        pause
        exit /b 1
    )
    type nul > "%MARKER%"
) else (
    echo [2/4] 依赖已就绪，跳过安装。
)

REM 3. 延迟打开浏览器（后台，不阻塞服务启动）
echo [3/4] 准备打开浏览器 %URL% ...
start "" cmd /c "timeout /t 2 /nobreak >nul & start %URL%"

REM 4. 启动 Flask 服务（python -m fapiao_helper）
echo [4/4] 启动服务（按 Ctrl+C 退出）...
echo ----------------------------------------
%PYTHON% -m fapiao_helper

pause
