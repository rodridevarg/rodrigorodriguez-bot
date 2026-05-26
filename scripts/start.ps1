#Requires -Version 5.1
<#
.SYNOPSIS
    Levanta FastAPI para la Secretaria Virtual de Rodrigo Rodriguez.
.DESCRIPTION
    - Verifica si FastAPI esta corriendo; si no, lo levanta en background.
    - Espera a que responda en /health.
    - Muestra estado final y URLs utiles.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = "$ProjectRoot\logs"
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"

# Crear carpeta de logs
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Test-FastApiRunning() {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -ErrorAction Stop -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Secretaria Virtual - START" -ForegroundColor Cyan
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
}

# FastAPI
Write-Host "[1/1] FastAPI..." -ForegroundColor Yellow
if (Test-FastApiRunning) {
    Write-Host "   Ya esta corriendo." -ForegroundColor Green
} else {
    Write-Host "   Levantando FastAPI en background..." -ForegroundColor DarkYellow
    Start-Process -FilePath $PythonExe `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$LogDir\fastapi.out.log" `
        -RedirectStandardError "$LogDir\fastapi.err.log"

    $attempts = 0
    $health = $null
    while (-not $health -and $attempts -lt 20) {
        Start-Sleep -Seconds 1
        try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -ErrorAction Stop -TimeoutSec 2 } catch {}
        $attempts++
        if ($attempts % 5 -eq 0) {
            Write-Host "   Esperando... ($attempts s)" -ForegroundColor DarkGray
        }
    }

    if (-not $health) {
        Write-Host "   ERROR: FastAPI no respondio. Revisa $LogDir\fastapi.err.log" -ForegroundColor Red
        exit 1
    }
    Write-Host "   FastAPI OK (modo: $($health.mode))." -ForegroundColor Green
}

# Estado final
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SERVICIOS ACTIVOS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Chat Web:   http://127.0.0.1:8000/chat" -ForegroundColor White
Write-Host "   Health:     http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host "   Webhook:    http://127.0.0.1:8000/webhook" -ForegroundColor White
Write-Host "   Ask API:    http://127.0.0.1:8000/ask-public" -ForegroundColor White
Write-Host "   Logs:       $LogDir\" -ForegroundColor White
Write-Host ""
Write-Host "   Para detener todo ejecuta: .\scripts\stop.ps1" -ForegroundColor DarkGray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
