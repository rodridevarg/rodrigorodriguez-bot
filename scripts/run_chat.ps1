#Requires -Version 5.1
<#
.SYNOPSIS
    Ejecuta el chat por consola de la Secretaria Virtual.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Secretaria Virtual - CHAT LOCAL" -ForegroundColor Cyan
Write-Host "  Rodrigo Rodriguez" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que existe el entorno virtual
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: No se encontro Python en $PythonExe" -ForegroundColor Red
    Write-Host "Ejecuta primero: python -m venv .venv" -ForegroundColor Red
    exit 1
}

# Verificar .env
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "WARNING: No se encontro .env" -ForegroundColor DarkYellow
    Write-Host "Copia .env.example a .env y completa tus credenciales." -ForegroundColor DarkYellow
    Write-Host ""
}

& $PythonExe "$ProjectRoot\app\chat_local.py"
