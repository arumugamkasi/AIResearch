@echo off
REM AIResearch Backend Startup Script for Windows

echo ==========================================
echo AIResearch Backend Server
echo ==========================================

REM Get the directory where this script is located
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0

REM Check if virtual environment exists
if not exist "%SCRIPT_DIR%airesearch_env" (
    echo Error: Virtual environment not found!
    echo Please run: python -m venv %SCRIPT_DIR%airesearch_env
    pause
    exit /b 1
)

REM Activate the virtual environment
call "%SCRIPT_DIR%airesearch_env\Scripts\activate.bat"

REM Check if .env file exists, create from example if not
if not exist "%SCRIPT_DIR%.env" (
    if exist "%SCRIPT_DIR%.env.example" (
        echo Creating .env from .env.example...
        copy "%SCRIPT_DIR%.env.example" "%SCRIPT_DIR%.env"
        echo Warning: Please update .env with your API keys if needed
    )
)

echo.
echo ^> Virtual environment activated
echo ^> Starting Flask server on http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ==========================================
echo.

REM Run the Flask app
python run.py
pause
