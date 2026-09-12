@echo off
setlocal
title SoulMate Agent

set "ROOT=%~dp0"
pushd "%ROOT%" || exit /b 1

echo ============================================================
echo   SoulMate Agent
echo ============================================================
echo.
echo [1/2] Starting API: http://127.0.0.1:8000 ...
start "SoulMate API" cmd /c "cd /d \"%ROOT%\" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
echo [2/2] Opening docs ...
start "" "http://127.0.0.1:8000/docs"
echo.
python scripts\agent_console.py
echo.
echo Press any key to close.
pause >nul
popd
endlocal
