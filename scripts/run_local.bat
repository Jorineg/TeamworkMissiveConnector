@echo off
REM Teamwork & Missive Connector - Local Development Runner for Windows

echo Starting Teamwork ^& Missive Connector...
echo.

REM Check if .env exists
if not exist .env (
    echo Error: .env file not found
    echo Please copy .env.example to .env and configure it
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Create directories
if not exist data\queue mkdir data\queue
if not exist data\checkpoints mkdir data\checkpoints
if not exist logs mkdir logs

echo.
echo Starting all services...
echo.
echo [1] Starting ngrok tunnel and backfill...
start "Teamwork-Missive: Startup/ngrok" cmd /c "python -m src.startup"

timeout /t 5 /nobreak >nul

echo [2] Starting Flask webhook server...
start "Teamwork-Missive: Flask App" cmd /c "python -m src.app"

timeout /t 2 /nobreak >nul

echo [3] Starting worker dispatcher...
start "Teamwork-Missive: Worker" cmd /c "python -m src.workers.dispatcher"

echo.
echo ========================================
echo All services started!
echo ========================================
echo.
echo Three windows have been opened:
echo   1. Startup/ngrok
echo   2. Flask webhook server
echo   3. Worker dispatcher
echo.
echo Check the Startup window for webhook URLs.
echo Logs are being written to: logs\app.log
echo.
echo To stop: Close all three windows
echo.
pause

