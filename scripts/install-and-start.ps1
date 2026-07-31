$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$root = Split-Path -Parent $PSScriptRoot
$dockerDownload = "https://www.docker.com/products/docker-desktop/"

function Pause-Guide {
    Write-Host ""
    [void](Read-Host "完成提示中的操作后，按 Enter 关闭窗口")
}

function Title([string]$text) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGreen
    Write-Host "  $text" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor DarkGreen
    Write-Host ""
}

function Test-DockerReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    & docker info --format "{{.ServerVersion}}" *> $null
    return $LASTEXITCODE -eq 0
}

function Show-SystemCheck {
    Write-Host "正在检查电脑环境..." -ForegroundColor Cyan
    $os = Get-CimInstance Win32_OperatingSystem
    Write-Host ("  Windows：{0} ({1})" -f $os.Caption, $os.Version)

    $dockerInstalled = [bool](Get-Command docker -ErrorAction SilentlyContinue)
    if ($dockerInstalled) {
        Write-Host "  Docker 命令：已安装" -ForegroundColor Green
    } else {
        Write-Host "  Docker Desktop：尚未安装" -ForegroundColor Yellow
    }

    try {
        $memoryGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
        Write-Host "  内存：${memoryGb} GB"
    } catch { }

    $port80 = Get-NetTCPConnection -LocalPort 80 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($port80) {
        Write-Host ("  80 端口：已被进程 {0} 使用，平台可能无法启动" -f $port80.OwningProcess) -ForegroundColor Yellow
    } else {
        Write-Host "  80 端口：可用" -ForegroundColor Green
    }
    Write-Host ""
}

try {
    Set-Location -LiteralPath $root
    Title "祁智运平台 · 安装与启动向导"
    Write-Host "这个向导会自动检查 Docker 并启动平台。" -ForegroundColor White
    Write-Host "第一次使用只需完成一次 Docker Desktop 安装，之后直接双击本文件即可。"
    Write-Host ""
    Show-SystemCheck

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "电脑尚未安装 Docker Desktop。" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "接下来会打开官方安装页面：" -ForegroundColor Cyan
        Write-Host "1. 点击 Download for Windows。"
        Write-Host "2. 使用默认选项安装。"
        Write-Host "3. 如果系统提示启用 WSL2 或重启，请按提示完成。"
        Write-Host "4. 安装完成后，再次双击【安装并启动祁智运平台.bat】。"
        Write-Host ""
        $open = Read-Host "按 Enter 打开官方安装页面，输入 N 取消"
        if ($open -notmatch '^(n|N)$') {
            Start-Process $dockerDownload
            Write-Host "已打开 Docker Desktop 官方页面。" -ForegroundColor Green
        }
        Pause-Guide
        exit 0
    }

    if (-not (Test-DockerReady)) {
        Write-Host "正在启动 Docker Desktop，请等待 1—2 分钟..." -ForegroundColor Cyan
        $desktop = @(
            (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
            (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if ($desktop) { Start-Process -FilePath $desktop -WindowStyle Hidden }
        for ($i = 1; $i -le 60; $i++) {
            Start-Sleep -Seconds 2
            if (Test-DockerReady) { break }
            if ($i % 10 -eq 0) { Write-Host ("  仍在等待 Docker Desktop（约 {0} 秒）..." -f ($i * 2)) }
        }
    }

    if (-not (Test-DockerReady)) {
        throw "Docker Desktop 尚未就绪。请打开 Docker Desktop，等状态显示为 Running 后，再次双击本文件。"
    }

    Write-Host "Docker Desktop 已就绪，正在启动祁智运平台..." -ForegroundColor Green
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\demo-control.ps1") -Action Start -NoPause
    if ($LASTEXITCODE -ne 0) { throw "平台启动失败，请双击【检查平台状态.bat】查看原因。" }
}
catch {
    Write-Host ""
    Write-Host "[未完成] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "如需帮助，请把此窗口截图发给维护人员。" -ForegroundColor Yellow
    Pause-Guide
    exit 1
}

