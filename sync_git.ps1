#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sincroniza el repositorio local con GitHub respetando siempre el .gitignore.
    Optimizado para ejecutarse desde cualquier ubicación mediante Alias.
#>

param(
    [string]$Message = ""
)

# ── ANCLAJE DE RUTA ───────────────────────────────────────────────────────────
# Forzamos la ejecución en la raíz del proyecto para que el Alias funcione siempre.
Set-Location "S:\dev\microtaller"

# ── Helpers de color ──────────────────────────────────────────────────────────
function Write-Ok  { param([string]$Text) Write-Host "  [OK] $Text" -ForegroundColor Green  }
function Write-Err { param([string]$Text) Write-Host "  [ERROR] $Text" -ForegroundColor Red   }
function Write-Step{ param([string]$Text) Write-Host "`n► $Text" -ForegroundColor Cyan        }

function Invoke-Step {
    param([string]$Label, [scriptblock]$Block)
    Write-Step $Label
    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Falló: $Label"
        exit $LASTEXITCODE
    }
    Write-Ok $Label
}

# ── Mensaje de commit ─────────────────────────────────────────────────────────
if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "Auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

# ── Verificar que estamos dentro de un repo Git ───────────────────────────────
Write-Step "Verificando repositorio Git..."
if (!(Test-Path .git)) {
    Write-Err "No se encontró un repositorio Git en: $(Get-Location)"
    exit 1
}
Write-Ok "Repositorio Git detectado en S:\dev\microtaller"

# ── 1. Higiene: limpiar índice para respetar .gitignore ───────────────────────
Invoke-Step "Limpiando índice Git (git rm -r --cached .)" {
    git rm -r --cached . --quiet
}

# ── 2. Indexar todos los archivos según .gitignore actualizado ────────────────
Invoke-Step "Indexando archivos (git add .)" {
    git add .
}

# ── 3. Verificar si hay cambios staged antes de commitear ─────────────────────
Write-Step "Verificando cambios staged..."
$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "  [INFO] No hay cambios para commitear. El árbol ya está limpio." -ForegroundColor Yellow
    exit 0
}
Write-Ok "Cambios detectados:"
$staged | ForEach-Object { Write-Host "         $_" -ForegroundColor Gray }

# ── 4. Commit con mensaje ─────────────────────────────────────────────────────
Invoke-Step "Commiteando: '$Message'" {
    git commit -m $Message
}

# ── 5. Push a main ────────────────────────────────────────────────────────────
Invoke-Step "Pushing a origin/main..." {
    git push origin main
}

# ── Resumen final ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "┌─────────────────────────────────────────────────┐" -ForegroundColor Green
Write-Host "│  Sync completado correctamente                  │" -ForegroundColor Green
Write-Host "│  Commit: $($Message.PadRight(35)) │" -ForegroundColor Green
Write-Host "└─────────────────────────────────────────────────┘" -ForegroundColor Green