param([switch]$Build)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env from .env.example (mock mode is ready without a key)."
}
$arguments = @("compose", "up", "-d")
if ($Build) { $arguments += "--build" }
& docker @arguments
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
& "$PSScriptRoot\verify.ps1"
