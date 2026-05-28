# Bot Multi-Cliente - Health Check y Capacidad (Windows)
# Uso: .\scripts\check_vps.ps1
# Solo lee estado local, no modifica nada.

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Health Check - Local (Windows)" -ForegroundColor Cyan
Write-Host "========================================"
Write-Host ""

# Recursos del sistema
Write-Host "--- Recursos del sistema ---" -ForegroundColor Yellow
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
$mem = Get-CimInstance Win32_OperatingSystem
$memTotal = [math]::Round($mem.TotalVisibleMemorySize / 1024)
$memFree = [math]::Round($mem.FreePhysicalMemory / 1024)
$estClientes = [math]::Floor($memFree / 300)

Write-Host "  CPU cores: $cpu"
Write-Host "  RAM total: ${memTotal}MB | disponible: ${memFree}MB"
Write-Host "  Estimado clientes nuevos (300MB c/u): ~$estClientes"

# Disco del proyecto
$disk = Get-PSDrive C | Select-Object Used, Free
$diskUsed = [math]::Round($disk.Used / 1GB, 2)
$diskFree = [math]::Round($disk.Free / 1GB, 2)
$diskPct = [math]::Round(($disk.Used / ($disk.Used + $disk.Free)) * 100, 1)
Write-Host "  Disco C: usado ${diskUsed}GB | libre ${diskFree}GB (${diskPct}% usado)"
Write-Host ""

# Verificar si Docker esta corriendo (opcional)
Write-Host "--- Docker (si aplica) ---" -ForegroundColor Yellow
try {
    $dockerInfo = docker info 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Docker: OK"
        docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}" 2>$null
    } else {
        Write-Host "  Docker: no disponible"
    }
} catch {
    Write-Host "  Docker: no instalado o no corriendo"
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NOTA: En local no hay limite estricto," -ForegroundColor Gray
Write-Host "  pero en VPS cada instancia usa ~300MB RAM." -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
