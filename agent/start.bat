@echo off
title SmartGuard Backend + Ngrok
cd /d "%~dp0"

echo ============================================
echo   SmartGuard 服务启动
echo ============================================
echo.

REM 激活虚拟环境并启动后端
echo [1/2] 启动后端服务...
call .venv\Scripts\activate
start "Backend" cmd /k "uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak > nul

REM 启动 ngrok
echo [2/2] 启动 ngrok 隧道...
echo.
echo ============================================
echo   复制下面的 ngrok 地址，填入 App 设置里
echo ============================================
echo.
ngrok http 8000
