@echo off
setlocal
title ETERNAL AI Trading Agent - System Launcher
color 0B

:: Check CLI arguments for direct automated startup
if /I "%1"=="model" goto START_AI_MODEL
if /I "%1"=="ai" goto START_AI_MODEL
if /I "%1"=="tunnel" goto START_AI_TUNNEL
if /I "%1"=="full" goto START_FULL_STACK
if /I "%1"=="all" goto START_FULL_STACK
if /I "%1"=="test" goto RUN_TESTS

:MAIN_MENU
cls
echo =================================================================
echo         ETERNAL AI TRADING AGENT - SYSTEM LAUNCHER
echo         Autonomous Machine Learning Engine for Indian Equities
echo =================================================================
echo.
echo   Please select what you want to start:
echo.
echo   [1] Start Localhost AI Model Server ONLY (Port 8001)
echo       * AI Model runs locally on this PC for Local or Direct queries.
echo.
echo   [2] Start Localhost AI Model + Cloud Tunnel (ngrok / Cloudflare)
echo       * RECOMMENDED for Render Backend + Vercel Frontend hosting!
echo.
echo   [3] Start Full-Stack System Locally (Port 8000)
echo       - Runs Local AI Model + Backend API + Web Dashboard UI.
echo.
echo   [4] Run Single Autonomous AI Prediction (CLI)
echo       - Shows Signal, Calibrated Confidence, and Explainable Reason.
echo.
echo   [5] Run 6-Month Pure RSI 9 and 14 Backtest (ETERNAL.NS)
echo.
echo   [6] Run Full Security and Cloud Deployment Verification Suite
echo.
echo   [7] Exit
echo.
echo =================================================================
set /p choice="Enter your choice [1-7] (Default is 2): "

if "%choice%"=="" set choice=2
if "%choice%"=="1" goto START_AI_MODEL
if "%choice%"=="2" goto START_AI_TUNNEL
if "%choice%"=="3" goto START_FULL_STACK
if "%choice%"=="4" goto RUN_CLI_PREDICT
if "%choice%"=="5" goto RUN_RSI_BACKTEST
if "%choice%"=="6" goto RUN_TESTS
if "%choice%"=="7" exit /b 0

echo Invalid choice, please enter 1 to 7.
timeout /t 2 >nul
goto MAIN_MENU


:START_AI_TUNNEL
call start_ai_tunnel.bat
goto END


:START_AI_MODEL
call start_ai_model.bat
goto END


:START_FULL_STACK
cls
title ETERNAL AI Trading Agent - Full Stack Dashboard [Port 8000]
color 0B
echo =================================================================
echo        LAUNCHING FULL STACK (AI + BACKEND + FRONTEND)
echo =================================================================
echo.

:: Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo [ERROR] Python is not found in system PATH!
    pause
    exit /b 1
)

echo [1/3] Verifying 6-Month Training and Local Weights...
python -c "from ai.auto_learner import auto_learner; auto_learner.ensure_initial_training(); print('       - AI Model Status: Ready on Localhost')"
echo.

echo [2/3] Starting FastAPI Server on http://localhost:8000...
echo       - Web Dashboard: http://localhost:8000
echo       - REST API Docs: http://localhost:8000/docs
echo.

:: Automatically open browser after 2 seconds
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

python cli.py server --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    color 0C
    echo [ERROR] Server exited with code %ERRORLEVEL%.
    pause
)
goto END


:RUN_CLI_PREDICT
cls
echo =================================================================
echo        RUNNING REAL-TIME AUTONOMOUS AI PREDICTION
echo =================================================================
echo.
python cli.py ai
echo.
if "%1" neq "" goto END
echo Press any key to return to menu...
pause >nul
goto MAIN_MENU


:RUN_RSI_BACKTEST
cls
echo =================================================================
echo        RUNNING 6-MONTH PURE RSI 9 and 14 BACKTEST
echo =================================================================
echo.
python cli.py backtest-rsi --range 6mo --interval 1h --qty 100
echo.
if "%1" neq "" goto END
echo Press any key to return to menu...
pause >nul
goto MAIN_MENU


:RUN_TESTS
cls
echo =================================================================
echo     RUNNING COMPREHENSIVE SECURITY AND DEPLOYMENT TESTS
echo =================================================================
echo.
python tests\test_security_and_deployment.py
echo.
if "%1" neq "" goto END
echo Press any key to return to menu...
pause >nul
goto MAIN_MENU


:END
exit /b 0
