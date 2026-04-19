@echo off
REM ============================================================
REM  Automated Senior PM Job Search — Windows Task Scheduler
REM  Schedule this bat file to run daily at 8:00 AM
REM
REM  To set up Task Scheduler:
REM  1. Open Task Scheduler (taskschd.msc)
REM  2. Create Basic Task → Name: "PM Job Search"
REM  3. Trigger: Daily at 8:00 AM
REM  4. Action: Start a Program
REM     Program: This bat file's full path
REM     Start in: d:\My AI playground\Apps I built\My job tracker
REM ============================================================

cd /d "d:\My AI playground\Apps I built\My job tracker"

echo ============================================================
echo  PM Job Search Pipeline — %date% %time%
echo ============================================================

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the pipeline
python main.py

echo.
echo Pipeline finished at %time%
echo ============================================================

REM Keep window open for 10 seconds to see results, then close
timeout /t 10
