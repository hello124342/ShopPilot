$ErrorActionPreference = "Stop"
if (-not $env:SHOPILOT_API_KEY) { throw "Set SHOPILOT_API_KEY before running the optional provider smoke." }
$env:SHOPILOT_RUNTIME_MODE = "agno"
$env:SHOPILOT_SIDE_EFFECT_MODE = "disabled"
& python -m shopilot.cli provider-smoke
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
