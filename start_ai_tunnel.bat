@echo off
setlocal
cd /d "%~dp0"
title ETERNAL AI Model Tunnel - Portable PC-to-Cloud Bridge [Port 8001]
color 0B

echo =================================================================
echo         ETERNAL AI MODEL - PORTABLE TUNNEL LAUNCHER
echo         Plug-and-Play AI Engine for Any Desktop / Laptop PC
echo =================================================================
echo.

:: 1. Detect Python
if exist "C:\Python314\python.exe" (
    set "PY_CMD=C:\Python314\python.exe"
) else if exist "C:\Python312\python.exe" (
    set "PY_CMD=C:\Python312\python.exe"
) else if exist "C:\Python311\python.exe" (
    set "PY_CMD=C:\Python311\python.exe"
) else (
    set "PY_CMD=python"
)

:: 2. Check Core Dependencies
echo [1/3] Checking Python Dependencies...
%PY_CMD% -c "import fastapi, pydantic, joblib, sklearn, pyngrok" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo       - Missing packages detected. Auto-installing from requirements.txt...
    %PY_CMD% -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        color 0C
        echo [ERROR] Failed to install requirements. Please run 'python -m pip install -r requirements.txt' manually.
        pause
        exit /b 1
    )
    echo       - All dependencies installed successfully!
) else (
    echo       - All Python dependencies verified!
)
echo.

:: 3. Verify Model and Training
if not defined PY_CMD if exist "C:\Python314\python.exe" (set "PY_CMD=C:\Python314\python.exe") else (set "PY_CMD=python")
echo [2/3] Checking AI Model Weights and Calibration...
%PY_CMD% -c "from ai.auto_learner import auto_learner; res = auto_learner.ensure_initial_training(); acc = res.get('accuracy'); hacc = res.get('high_conf_accuracy'); print('       - AI Status: Ready | Signal Win Rate: ' + (str(acc) + '%% (Balanced OOS)' if acc is not None else 'N/A') + ' | High-Conf Conviction: ' + (str(hacc) + '%%' if hacc is not None else 'N/A'))"
echo.

:: 4. Launch Portable Tunnel Manager and Handshake Coordinator
if not defined PY_CMD if exist "C:\Python314\python.exe" (set "PY_CMD=C:\Python314\python.exe") else (set "PY_CMD=python")
echo [3/3] Starting AI Model Microservice and Cloud Bridge...
echo =================================================================
echo   * Local AI Server:       http://127.0.0.1:8001
echo   * Handshake Engine:      ai\tunnel_manager.py
echo.
echo   PORTABLE ZERO-CONFIG ARCHITECTURE:
echo      1. Starts the AI model on Port 8001.
echo      2. Automatically opens a public HTTPS tunnel (ngrok / Cloudflare).
echo      3. Automatically registers its URL with your deployed Render Backend.
echo      4. Keeps Render awake with continuous heartbeats.
echo.
echo   [TIP] If you need to add your free ngrok token:
echo         Add NGROK_AUTHTOKEN=your_token in .env or run:
echo         ngrok config add-authtoken YOUR_TOKEN_HERE
echo.
echo   Press Ctrl+C to terminate.
echo =================================================================
echo.

%PY_CMD% ai\tunnel_manager.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    color 0C
    echo [ERROR] AI Tunnel Manager stopped with code %ERRORLEVEL%.
    pause
)
