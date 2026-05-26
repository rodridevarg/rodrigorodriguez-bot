@echo off
chcp 65001 >nul
echo ========================================
echo   Secretaria Virtual - START
echo   Rodrigo Rodriguez
echo ========================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
echo.
pause
