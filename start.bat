@echo off
REM AIResearch Startup Script for Windows

echo ========================================
echo AIResearch - Startup Script
echo ========================================

REM Check if backend and frontend folders exist
if not exist "backend" (
    echo Error: backend directory not found
    exit /b 1
)
if not exist "frontend" (
    echo Error: frontend directory not found
    exit /b 1
)

REM Start backend
echo.
echo Starting Backend...
cd backend

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv and install requirements
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

REM Start Flask server
start python run.py
echo Backend started on http://localhost:5000

REM Return to project root
cd ..

REM Wait for backend to start
timeout /t 3 /nobreak

REM Start frontend
echo.
echo Starting Frontend...
cd frontend

REM Install dependencies if node_modules doesn't exist
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install --quiet
)

REM Start React development server
start npm start
echo Frontend starting on http://localhost:3000

echo.
echo ========================================
echo Both servers are starting!
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000
echo ========================================

cd ..
pause
