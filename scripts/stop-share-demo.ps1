$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$stateDirectory = Join-Path $env:LOCALAPPDATA "QizhiYun"
$pidFile = Join-Path $stateDirectory "cloudflared.pid"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGreen
Write-Host "  祁智运平台 · 停止分享链接" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkGreen
Write-Host ""

$stopped = $false
if (Test-Path -LiteralPath $pidFile) {
    $savedPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($savedPid -match '^\d+$') {
        $process = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq "cloudflared") {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

if ($stopped) {
    Write-Host "公网分享链接已停止。" -ForegroundColor Green
}
else {
    Write-Host "没有找到由祁智运平台启动的分享链接。" -ForegroundColor Yellow
}
Write-Host ""
[void](Read-Host "按 Enter 关闭此窗口")
