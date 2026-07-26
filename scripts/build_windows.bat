@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error

set QT_QPA_PLATFORM=offscreen
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto :error
set QT_QPA_PLATFORM=

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name "秋招进程台账" main.py
if errorlevel 1 goto :error

echo.
echo 打包完成：%CD%\dist\秋招进程台账\秋招进程台账.exe
exit /b 0

:error
echo.
echo 测试或打包失败，请查看上方错误信息。
pause
exit /b 1
