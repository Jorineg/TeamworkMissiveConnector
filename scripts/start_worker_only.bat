@echo off
REM Start only the worker to process existing queue

echo Starting worker dispatcher...

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python -m src.workers.dispatcher

