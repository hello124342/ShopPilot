param([string]$BaseUrl = "http://127.0.0.1:8000")
$ErrorActionPreference = "Stop"
$campaign = @{
    product = "持久化验证商品"; brand = "ShopPilot QA"; target_audience = "本地测试用户"
    platform = "xiaohongshu"; goal = "验证容器重启"; constraints = @("不得真实发布")
} | ConvertTo-Json
$created = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/runs" -ContentType "application/json" -Body $campaign
& docker compose restart app
if ($LASTEXITCODE -ne 0) { throw "Container restart failed" }
& "$PSScriptRoot\verify.ps1" -BaseUrl $BaseUrl
$restored = Invoke-RestMethod -Uri "$BaseUrl/api/runs/$($created.run_id)"
if ($restored.run_id -ne $created.run_id) { throw "Persistence verification failed" }
Write-Host "Persistence verified for run $($created.run_id)"
