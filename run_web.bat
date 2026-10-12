@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "REPOSNIPY_NO_BROWSER=1"

set "BASEPY="
for /f "delims=" %%P in ('dir /b /s "%~dp0Python310\python.exe" 2^>nul') do if not defined BASEPY set "BASEPY=%%P"
if not defined BASEPY (
    echo [错误] 找不到项目自带的 Python310，请确认文件夹是完整复制的。
    pause
    exit /b 1
)
"%BASEPY%" "%~dp0bootstrap.py"
if errorlevel 1 (
    pause
    exit /b 1
)

echo Starting API on port 8000 in a new window...
start "RepoSnipy API" cmd /k ""%~dp0.venv\Scripts\python.exe" "%~dp0serve.py""
ping -n 6 127.0.0.1 >nul

cd /d "%~dp0frontend"
if not exist node_modules (
    echo Installing frontend dependencies for the first run...
    call npm install
)
echo Dev server: http://localhost:5173
start "" http://localhost:5173/
call npm run dev
