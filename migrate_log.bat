@echo off
setlocal

echo Migrating monitor.log to monitor.db...

if not exist ".venv" (
    echo ERROR: Virtual environment not found. Run run.bat first to set it up.
    pause
    exit /b 1
)

.venv\Scripts\python migrate_log_to_db.py
pause
