$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& python -m shopilot.cli scenarios
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
