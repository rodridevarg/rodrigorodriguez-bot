#Requires -Version 5.1
<#
.SYNOPSIS
    Detiene todos los servicios de la Secretaria Virtual.
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Secretaria Virtual - STOP" -ForegroundColor Cyan
Write-Host "  Rodrigo Rodriguez" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$killed = $false

# Detener FastAPI (buscar python con uvicorn o app.main en la linea de comando)
$pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*app.main*"
}
if ($pythonProcs) {
    Write-Host "[1/1] Deteniendo FastAPI (python uvicorn)..." -ForegroundColor Yellow
    $pythonProcs | Stop-Process -Force
    Write-Host "   Detenido." -ForegroundColor Green
    $killed = $true
} else {
    Write-Host "[1/1] FastAPI no estaba corriendo." -ForegroundColor DarkGray
}

Write-Host ""
if ($killed) {
    Write-Host "Todos los servicios fueron detenidos." -ForegroundColor Green
} else {
    Write-Host "No habia servicios activos." -ForegroundColor DarkYellow
}
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
