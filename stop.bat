@echo off
chcp 65001 >nul
echo ========================================
echo   Secretaria Virtual - STOP
echo   Rodrigo Rodriguez
echo ========================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
echo.
pause
