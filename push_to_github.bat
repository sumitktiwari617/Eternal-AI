@echo off
setlocal
cd /d "%~dp0"
title Push ETERNAL AI to GitHub (sumitktiwari617/Eternal-AI)
color 0B

echo =================================================================
echo         PUSH ETERNAL AI TO GITHUB
echo         Target: https://github.com/sumitktiwari617/Eternal-AI.git
echo =================================================================
echo.
echo   Current Branch: main
echo   Commits Ready:  Phase 1 + 3-Tier Deployment + Clean Docs
echo.

git remote set-url origin https://github.com/sumitktiwari617/Eternal-AI.git
git branch -M main

echo   Attempting to push to origin main...
echo   (If Git Credential Manager prompts in your browser, click Authorize)
echo.

git push -u origin main

if %ERRORLEVEL% EQU 0 (
    color 0A
    echo.
    echo =================================================================
    echo   SUCCESS! All code is pushed to:
    echo   https://github.com/sumitktiwari617/Eternal-AI
    echo =================================================================
    pause
    exit /b 0
)

echo.
color 0E
echo =================================================================
echo   NOTE: If GitHub gave 'Permission denied' or authentication error:
echo.
echo   Please authenticate securely with Git Credential Manager:
echo     1. Run: git credential-manager github login
echo     2. Or authorize via browser window prompt
echo =================================================================
echo.
pause
exit /b 1

