# upgrade_model.ps1 (Versión Robusta para Aliases)
param(
    [string]$Message = ""
)

# 1. Saltamos a la carpeta backend sin importar el origen
Set-Location "S:\dev\microtaller\backend"

# 2. Activamos el entorno virtual automáticamente
# Esto asegura que Alembic tenga acceso a tus modelos de Python (currency, vehicle, etc.)
& "S:\dev\microtaller\backend\.venv\Scripts\Activate.ps1"

# ── Resolve migration message ─────────────────────────────────────────────────
if ([string]::IsNullOrWhiteSpace($Message)) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmm"
    $Message = "auto_migration_$timestamp"
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan
Write-Host "   MicroTaller — Alembic Model Upgrade" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan
Write-Host "   Message : $Message" -ForegroundColor White
Write-Host ""

# ── Step 1: autogenerate revision ─────────────────────────────────────────────
Write-Host "[1/2] Generating migration script..." -ForegroundColor Yellow

# Ejecutamos alembic directamente (el venv ya está activo por el paso 2)
alembic revision --autogenerate -m "$Message"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] alembic revision failed. Check the output above." -ForegroundColor Red
    exit 1
}

# ── Step 2: apply migration ───────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/2] Applying migration (upgrade head)..." -ForegroundColor Yellow
alembic upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] alembic upgrade head failed. Check the output above." -ForegroundColor Red
    exit 1
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGreen
Write-Host "   [OK] Modelo y base de datos sincronizados." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGreen
Write-Host ""