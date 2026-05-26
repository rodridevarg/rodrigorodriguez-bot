#Requires -Version 5.1
<#
.SYNOPSIS
    Muestra el estado actual de los servicios de la Secretaria Virtual.
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Secretaria Virtual - STATUS" -ForegroundColor Cyan
Write-Host "  Rodrigo Rodriguez" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# FastAPI
$pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*app.main*"
}
if ($pythonProcs) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -ErrorAction Stop -TimeoutSec 3
        Write-Host "[FastAPI] RUNNING (mode: $($health.mode))" -ForegroundColor Green
        Write-Host "          Local:  http://127.0.0.1:8000/health" -ForegroundColor White
        Write-Host "          Chat:   http://127.0.0.1:8000/chat" -ForegroundColor White
    } catch {
        Write-Host "[FastAPI] RUNNING (no responde en :8000)" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "[FastAPI] STOPPED" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Comandos utiles:" -ForegroundColor Cyan
Write-Host "    .\scripts\start.ps1  -> Levantar todo" -ForegroundColor White
Write-Host "    .\scripts\stop.ps1   -> Detener todo" -ForegroundColor White
Write-Host "    .\scripts\status.ps1 -> Ver estado" -ForegroundColor White
Write-Host "    .\scripts\run_chat.ps1 -> Chat por consola" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
