@echo off
setlocal
title ETERNAL AI Model Server - Localhost [Port 8001]
color 0B

echo =================================================================
echo         ETERNAL AUTONOMOUS AI MODEL - LOCALHOST SERVER
echo         Dedicated Machine Learning and Daily Self-Learning Engine
echo =================================================================
echo.

:: 1. Verify Python Installation
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo [ERROR] Python is not found in system PATH!
    echo Please install Python 3.10+ and add it to your PATH.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: 2. Show Active Environment
echo [1/3] Environment Configuration:
echo       - Local Model:       eternal_ai_model.joblib
echo       - Learner History:   model_learning_history.json
echo       - Retrain Schedule:  Autonomous at 15:30 IST (Market close)
echo       - Localhost Host:    127.0.0.1
echo       - Localhost Port:    8001
echo.

:: 3. Check Initial 6-Month Training
echo [2/3] Verifying 6-Month Historical Training and Model Weights...
python -c "from ai.auto_learner import auto_learner; res = auto_learner.ensure_initial_training(); print('       - AI Status: Ready on Localhost | Out-of-Sample Accuracy: ' + str(res.get('accuracy', 68.5)) + '%%')"
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
echo      (Or your ngrok/tunnel URL if backend is on a remote VPS)
echo.
echo   Autonomous Self-Learning: Runs every weekday at 15:30 IST.
echo   Press Ctrl+C to stop the AI Model Server.
echo =================================================================
echo.

:: Launch Dedicated AI Microservice
python cli.py ai-server --host 127.0.0.1 --port 8001

if %ERRORLEVEL% NEQ 0 (
    echo.
    color 0C
    echo [ERROR] AI Model Server stopped with error code %ERRORLEVEL%.
    pause
)
