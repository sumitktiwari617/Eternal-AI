@echo off
setlocal
cd /d "%~dp0"
title ETERNAL AI - One-Click Shutdown [Close All Ports and Tunnels]
color 0C

echo =================================================================
echo         ETERNAL AI - ONE-CLICK SYSTEM SHUTDOWN
echo         Stopping Tunnels and AI Microservices...
echo =================================================================
echo.

:: 1. Terminate Tunnel Processes
echo [1/3] Closing OpenSSH ^& Tunnel Bridges...
taskkill /F /IM ssh.exe >nul 2>&1
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM cloudflared.exe >nul 2>&1
echo       - All tunnel processes terminated.

:: 2. Terminate Local AI Server and Backend Processes
echo.
echo [2/3] Stopping Local AI Server (Port 8001) and Backend (Port 8000)...
powershell -NoProfile -Command "Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'ai-server|tunnel_manager|cli.py server' } | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1
echo       - Local Python AI microservices stopped.

:: 3. Verify Sockets Closed
echo.
echo [3/3] Verifying Sockets...
powershell -NoProfile -Command "$ports = Get-NetTCPConnection -LocalPort 8000, 8001, 4040 -ErrorAction SilentlyContinue; if ($ports) { Write-Host '       [!] Freeing remaining ports...' -ForegroundColor Yellow; $ports | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } else { Write-Host '       - All ports (8000, 8001, 4040) are completely CLOSED.' -ForegroundColor Green }"

echo.
echo =================================================================
color 0A
echo   [+] SUCCESS: AI TUNNEL ^& LOCAL SERVERS ARE NOW OFFLINE!
echo       Your laptop is clean. Render cloud backend is in standby.
echo =================================================================
echo.
ping 127.0.0.1 -n 3 >nul 2>&1
exit /b 0
