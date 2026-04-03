param(
    [switch]$SkipMigrate
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvActivate = Join-Path $projectRoot ".venv\Scripts\Activate.ps1"
$apiDir = Join-Path $projectRoot "apps\api"

function Write-Step {
    param([string]$Message)
    Write-Host "[dev] $Message" -ForegroundColor Cyan
}

if (-not (Test-Path $venvActivate)) {
    throw "Missing virtual environment activation script: $venvActivate. Run 'uv venv' in the project root first."
}

Write-Step "Project root: $projectRoot"

if (-not $SkipMigrate) {
    Write-Step "Running alembic upgrade head"
    Set-Location $apiDir
    & $venvActivate
    alembic upgrade head
    Set-Location $projectRoot
} else {
    Write-Step "Skipping database migration"
}

$apiCommand = @"
Set-Location '$projectRoot'
& '$venvActivate'
python -m uvicorn app.main:app --reload --app-dir apps/api
"@

$webCommand = @"
Set-Location '$projectRoot'
pnpm dev:web
"@

Write-Step "Starting API window"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $apiCommand
)

Write-Step "Starting web window"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $webCommand
)

Write-Step "API and web windows started"
