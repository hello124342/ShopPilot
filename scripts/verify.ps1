param([string]$BaseUrl = "http://127.0.0.1:8000", [int]$Attempts = 20)
$ErrorActionPreference = "Stop"
for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    try {
        $live = Invoke-RestMethod -Uri "$BaseUrl/health/live" -TimeoutSec 3
        $ready = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 3
        Write-Host "ShopPilot $($live.status); runtime=$($ready.runtime.runtime_mode); readiness=$($ready.status)"
        exit 0
    } catch {
        if ($attempt -eq $Attempts) { throw "ShopPilot health verification failed: $($_.Exception.Message)" }
        Start-Sleep -Seconds 2
    }
}
