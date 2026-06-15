@echo off
REM Run the entire INVINCIBLE RAG project in one command
REM This script starts both the FastAPI backend and React frontend

setlocal enabledelayedexpansion

echo Starting INVINCIBLE RAG Project...
echo.

REM Start Backend (FastAPI)
echo Starting Backend API on port 8000...
start cmd /k ".venv\Scripts\activate.bat && uvicorn api:app --host 0.0.0.0 --port 8000"

REM Give backend a moment to start
timeout /t 2 /nobreak

REM Start Frontend (React/Vite)
echo Starting Frontend on port 5173...
start cmd /k "cd frontend && npm run dev"

echo.
echo ============================================
echo Backend API: http://localhost:8000
echo Frontend:    http://localhost:5173
echo ============================================
echo.
echo Both services are starting in separate windows.
echo Close either window to stop that service.
echo.
pause
