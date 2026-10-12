@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 先找项目自带的基础解释器（它不依赖虚拟环境，venv 坏了也能用）
set "BASEPY="
for /f "delims=" %%P in ('dir /b /s "%~dp0Python310\python.exe" 2^>nul') do if not defined BASEPY set "BASEPY=%%P"
if not defined BASEPY (
    echo [错误] 找不到项目自带的 Python310，请确认文件夹是完整复制的。
    pause
    exit /b 1
)

rem 自检并修复虚拟环境（换目录/换电脑后第一次运行会用到）
"%BASEPY%" "%~dp0bootstrap.py"
if errorlevel 1 (
    pause
    exit /b 1
)

".venv\Scripts\python.exe" serve.py
pause
