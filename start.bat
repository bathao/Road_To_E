@echo off
REM ============================================================================
REM  Table Tennis Coach - one-click launcher (Windows)
REM  - installs backend + frontend deps on first run
REM  - rebuilds the frontend fresh (clears old dist so the browser gets new code)
REM  - starts the FastAPI server on port 8000
REM  - opens a new Chrome tab at the app
REM ============================================================================
setlocal
cd /d "%~dp0"

set PORT=8000
set BACKEND=%~dp0backend
set FRONTEND=%~dp0frontend
set VENV=%BACKEND%\.venv

echo.
echo [1/4] Checking backend virtual environment...
if not exist "%VENV%\Scripts\python.exe" (
    echo     Creating venv and installing backend dependencies...
    python -m venv "%VENV%"
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
    "%VENV%\Scripts\python.exe" -m pip install -r "%BACKEND%\requirements.txt"
)

echo.
echo [2/4] Checking frontend dependencies...
if not exist "%FRONTEND%\node_modules" (
    echo     Installing frontend dependencies...
    pushd "%FRONTEND%"
    call npm install
    popd
)

echo.
echo [3/4] Building frontend (fresh build, clears old cache)...
if exist "%FRONTEND%\dist" rmdir /s /q "%FRONTEND%\dist"
pushd "%FRONTEND%"
call npm run build
popd

echo.
echo [4/4] Starting server and opening browser...
REM Open a NEW Chrome tab at the app once the server has a moment to boot.
start "" cmd /c "timeout /t 3 >nul && start chrome http://localhost:%PORT%"

REM Run uvicorn in the foreground (Ctrl+C to stop).
"%VENV%\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%BACKEND%" --host 127.0.0.1 --port %PORT%

endlocal
