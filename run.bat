@echo off
title ARGUS — It Never Stops Watching
color 0A
echo.
echo  ============================================
echo   A R G U S   -   Starting up...
echo  ============================================
echo.
echo  [1/3] Activating environment...
call venv\Scripts\activate
echo.
echo  [2/3] Starting backend server...
start "ARGUS Backend" cmd /k "call venv\Scripts\activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo  [3/3] Waiting for backend to initialize...
timeout /t 4 /nobreak > nul
echo.
echo  Launching ARGUS client...
echo.
python client/argus_client.py
pause
