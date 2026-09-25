@echo off
REM ============================================================================
REM  Road To E - sync the database snapshot to the shared read-only copy
REM  1. checkpoint the SQLite WAL + stamp backend/data/last_sync.txt
REM  2. commit ONLY the DB + stamp (code changes stay untouched)
REM  3. push to GitHub -> Render rebuilds the shared copy (~3-5 minutes)
REM  Safe to run while start.bat is running.
REM ============================================================================
setlocal
cd /d "%~dp0"

set PY=%~dp0backend\.venv\Scripts\python.exe
if not exist "%PY%" (
    echo Backend venv not found - run start.bat once first.
    goto :fail
)

echo.
echo [1/3] Checkpointing the database and stamping the sync time...
"%PY%" backend\scripts\sync_prepare.py
if errorlevel 1 goto :fail

echo.
echo [2/3] Committing the database snapshot...
git add backend/data/tabletennis.db backend/data/last_sync.txt
git diff --cached --quiet -- backend/data/tabletennis.db
if not errorlevel 1 (
    echo     No new data since the last sync - nothing to push.
    git reset -q -- backend/data/last_sync.txt
    git checkout -q -- backend/data/last_sync.txt
    goto :done
)
for /f %%i in ('"%PY%" -c "import datetime;print(datetime.date.today())"') do set TODAY=%%i
git commit -q -m "DB sync %TODAY%" -- backend/data/tabletennis.db backend/data/last_sync.txt
if errorlevel 1 goto :fail

echo.
echo [3/3] Pushing to GitHub (Render redeploys the shared copy automatically)...
git push origin master
if errorlevel 1 goto :fail

:done
echo.
echo Done.
pause
exit /b 0

:fail
echo.
echo SYNC FAILED - see the messages above. Nothing was pushed.
pause
exit /b 1
