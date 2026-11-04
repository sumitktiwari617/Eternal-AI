@echo off
setlocal
cd /d "%~dp0"
title ETERNAL AI Trading Agent - System Launcher
color 0B

:: Robust Python detection
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

:: Check CLI arguments for direct automated startup
if /I "%1"=="tunnel" goto START_AI_TUNNEL
if /I "%1"=="model" goto START_AI_MODEL
if /I "%1"=="ai" goto RUN_CLI_PREDICT
if /I "%1"=="full" goto START_FULL_STACK
if /I "%1"=="all" goto START_FULL_STACK
if /I "%1"=="test" goto RUN_TESTS

:MAIN_MENU
cls
echo =================================================================
echo         ETERNAL AI TRADING AGENT - SYSTEM LAUNCHER
echo         Autonomous Advisory Engine for Indian Equities (NSE)
echo =================================================================
echo.
echo   Please select an option:
echo.
echo   [1] Start Laptop AI Model + Cloud Tunnel (ngrok to Render) [DEFAULT]
echo       * Runs AI model on Port 8001, opens HTTPS tunnel, and connects
echo         automatically to your deployed Render Backend!
echo.
echo   [2] Start Localhost AI Model Server ONLY (Port 8001)
echo       * Dedicated AI Microservice on this machine without external tunnel.
echo.
echo   [3] Start Full-Stack System Locally (Port 8000)
echo       * Runs AI Model + FastAPI Backend + Web Dashboard on http://localhost:8000
echo.
echo   [4] Run Verification Test Suite (pytest)
echo       * Runs comprehensive safety, truthfulness, and deployment tests.
echo.
echo   [5] Run Single Autonomous AI Prediction (CLI)
echo       * Evaluates live market conditions and outputs signal & ATR brackets.
echo.
echo   [6] Exit
echo.
echo =================================================================
set /p choice="Enter your choice [1-6] (Default is 1): "

if "%choice%"=="" set choice=1
if "%choice%"=="1" goto START_AI_TUNNEL
if "%choice%"=="2" goto START_AI_MODEL
if "%choice%"=="3" goto START_FULL_STACK
if "%choice%"=="4" goto RUN_TESTS
if "%choice%"=="5" goto RUN_CLI_PREDICT
if "%choice%"=="6" exit /b 0

echo Invalid choice, please enter 1 to 6.
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

echo [1/3] Verifying Training and Local Weights...
%PY_CMD% -c "from ai.auto_learner import auto_learner; auto_learner.ensure_initial_training(); print('       - AI Model Status: Ready on Localhost')"
echo.

echo [2/3] Starting FastAPI Server on http://localhost:8000...
echo       - Web Dashboard: http://localhost:8000
echo       - REST API Docs: http://localhost:8000/docs
echo.

:: Automatically open browser after 2 seconds
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

%PY_CMD% cli.py server --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    color 0C
    echo [ERROR] Server exited with code %ERRORLEVEL%.
    pause
)
goto END


:RUN_TESTS
cls
echo =================================================================
echo     RUNNING COMPREHENSIVE SAFETY AND DEPLOYMENT TESTS
echo =================================================================
echo.
%PY_CMD% -m pytest tests/
echo.
if "%1" neq "" goto END
echo Press any key to return to menu...
pause >nul
goto MAIN_MENU


:RUN_CLI_PREDICT
cls
echo =================================================================
echo        RUNNING REAL-TIME AUTONOMOUS AI PREDICTION
echo =================================================================
echo.
%PY_CMD% cli.py ai
echo.
if "%1" neq "" goto END
echo Press any key to return to menu...
pause >nul
goto MAIN_MENU


:END
exit /b 0
