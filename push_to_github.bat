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
echo   NOTE: If GitHub gave 'Permission denied to ankitkumarojha-29':
echo.
echo   EASIEST SOLUTION (Takes 30 seconds):
echo     1. Open this link in your browser:
echo        https://github.com/sumitktiwari617/Eternal-AI/settings/access
echo     2. Click 'Add people' and invite: ankitkumarojha-29
echo     3. Press any key here to retry push!
echo.
echo   ALTERNATIVE SOLUTION:
echo     If you have a GitHub Personal Access Token (PAT) for sumitktiwari617,
echo     paste it below:
echo =================================================================
echo.
set /p pat="Enter GitHub Personal Access Token (or hit Enter to retry): "

if not "%pat%"=="" (
    echo.
    echo Pushing with provided token...
    git push https://%pat%@github.com/sumitktiwari617/Eternal-AI.git main
    if %ERRORLEVEL% EQU 0 (
        color 0A
        echo.
        echo =================================================================
        echo   SUCCESS! Pushed with token to:
        echo   https://github.com/sumitktiwari617/Eternal-AI
        echo =================================================================
        pause
        exit /b 0
    )
) else (
    echo.
    echo Retrying push...
    git push -u origin main
)

echo.
pause

