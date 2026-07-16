param(
    [switch]$Build,
    [switch]$Detach,
    [ValidateSet("dev", "prod")]
    [string]$Mode = "dev"
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Test-Path ".env")) {
    Write-Host "No .env file found. Copying .env.example -> .env" -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Edit .env with your API keys before running." -ForegroundColor Yellow
}

$composeArgs = @("-f", "docker-compose.yml")
if ($Mode -eq "prod") {
    $composeArgs += "-f", "infra/docker-compose.yml"
}
if ($Build) {
    $composeArgs += "--build"
}
if ($Detach) {
    $composeArgs += "-d"
}

$composeArgs += "up"

Write-Host "Starting FIOS in $Mode mode..." -ForegroundColor Cyan
Write-Host "docker compose $($composeArgs -join ' ')" -ForegroundColor Gray

docker compose @composeArgs
