@echo off
setlocal
cd /d "%~dp0"
title ETERNAL AI Model Server - Localhost [Port 8001]
color 0B

echo =================================================================
echo         ETERNAL AUTONOMOUS AI MODEL - LOCALHOST SERVER
echo         Dedicated Machine Learning and Daily Self-Learning Engine
echo =================================================================
echo.

:: 1. Detect Python
set "PY_CMD=python"
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PY_CMD=py"
    ) else if exist "C:\Python314\python.exe" (
        set "PY_CMD=C:\Python314\python.exe"
    ) else if exist "C:\Python312\python.exe" (
        set "PY_CMD=C:\Python312\python.exe"
    ) else if exist "C:\Python311\python.exe" (
        set "PY_CMD=C:\Python311\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) else (
        color 0C
        echo [ERROR] Python was not found in your system PATH!
        echo Please install Python 3.10+ from https://www.python.org/downloads/
        echo Make sure to check 'Add Python to PATH' during installation.
        pause
        exit /b 1
    )
)

:: 2. Show Active Environment
echo [1/3] Environment Configuration:
echo       - Local Model:       eternal_ai_model.joblib
echo       - Learner History:   model_learning_history.json
echo       - Retrain Schedule:  Autonomous at 15:30 IST (Market close)
echo       - Localhost Host:    127.0.0.1
echo       - Localhost Port:    8001
echo.

:: 3. Check Initial Training
echo [2/3] Verifying Historical Training and Model Weights...
%PY_CMD% -c "from ai.auto_learner import auto_learner; res = auto_learner.ensure_initial_training(); acc = res.get('accuracy'); print('       - AI Status: Ready on Localhost | Out-of-Sample Accuracy: ' + (str(acc) + '%%' if acc is not None else 'N/A'))"
if %ERRORLEVEL% NEQ 0 (
    color 0E
    echo [WARNING] Initial auto-train check returned a non-zero code, continuing startup...
    color 0B
)
echo.

:: 4. Start Localhost AI Model Microservice
echo [3/3] Launching Local AI Model Server on Port 8001...
echo =================================================================
echo   * LOCAL AI MODEL IS NOW ONLINE AND READY!
echo   ---------------------------------------------------------------
echo   * Health Probe:       http://127.0.0.1:8001/health
echo   * Live Prediction:    http://127.0.0.1:8001/api/ai/predict
echo   * Swagger API Docs:   http://127.0.0.1:8001/docs
echo   * Accuracy History:   http://127.0.0.1:8001/api/ai/accuracy-trend
echo.
echo   For Cloud-Hosted Backend/Frontend:
echo      Point AI_MODEL_SERVICE_URL to: http://127.0.0.1:8001
echo      (Or use start_ai_tunnel.bat to create an automatic cloud bridge)
echo.
echo   Autonomous Self-Learning: Runs every weekday at 15:30 IST.
echo   Press Ctrl+C to stop the AI Model Server.
echo =================================================================
echo.

:: Launch Dedicated AI Microservice
%PY_CMD% cli.py ai-server --host 127.0.0.1 --port 8001

if %ERRORLEVEL% NEQ 0 (
    echo.
    color 0C
    echo [ERROR] AI Model Server stopped with error code %ERRORLEVEL%.
    pause
)
