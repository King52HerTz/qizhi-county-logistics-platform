param(
    [ValidateSet("Start", "Stop", "Status", "Reset")]
    [string]$Action = "Start",
    [switch]$NoPause,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$projectRoot = Split-Path -Parent $PSScriptRoot
$appUrl = "http://127.0.0.1"
$healthUrl = "$appUrl/api/v1/health/ready"

function Write-Title {
    param([string]$Text)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGreen
    Write-Host "  $Text" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor DarkGreen
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "[正在处理] $Text" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "[完成] $Text" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Text)
    Write-Host "[未完成] $Text" -ForegroundColor Red
}

function Wait-ForExit {
    if ($NoPause) {
        return
    }
    Write-Host ""
    [void](Read-Host "按 Enter 键关闭此窗口")
}

function Find-DockerDesktop {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Test-DockerEngine {
    & docker info --format "{{.ServerVersion}}" *> $null
    return $LASTEXITCODE -eq 0
}

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Failure "未检测到 Docker Desktop。"
        Write-Host "本平台不需要安装 Python、Node.js 或数据库，但需要先安装一次 Docker Desktop。"
        Write-Host "下载地址将自动在浏览器中打开，安装时保持默认选项即可。"
        Start-Process "https://www.docker.com/products/docker-desktop/"
        throw "请安装并启动 Docker Desktop 后，再双击【启动祁智运平台.bat】。"
    }

    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose 不可用，请更新 Docker Desktop 后重试。"
    }

    if (Test-DockerEngine) {
        Write-Success "Docker Desktop 已运行"
        return
    }

    $dockerDesktop = Find-DockerDesktop
    if (-not $dockerDesktop) {
        throw "已安装 Docker 命令，但未找到 Docker Desktop，请手动启动 Docker Desktop。"
    }

    Write-Step "正在自动启动 Docker Desktop，首次启动可能需要 1—2 分钟"
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        Start-Sleep -Seconds 2
        if (Test-DockerEngine) {
            Write-Success "Docker Desktop 已就绪"
            return
        }
        if ($attempt % 5 -eq 0) {
            Write-Host "  仍在等待 Docker Desktop（$($attempt * 2) 秒）..."
        }
    }
    throw "Docker Desktop 启动超时，请确认它已正常运行后重试。"
}

function Ensure-EnvironmentFile {
    $environmentFile = Join-Path $projectRoot ".env"
    $exampleFile = Join-Path $projectRoot ".env.example"
    if (-not (Test-Path -LiteralPath $environmentFile)) {
        if (-not (Test-Path -LiteralPath $exampleFile)) {
            throw "缺少 .env.example，项目文件可能不完整。"
        }
        Copy-Item -LiteralPath $exampleFile -Destination $environmentFile
        Write-Success "已自动生成本地运行配置"
    }
}

function Backup-Database {
    $backupDirectory = Join-Path $projectRoot "backups"
    if (-not (Test-Path -LiteralPath $backupDirectory)) {
        New-Item -ItemType Directory -Path $backupDirectory | Out-Null
    }
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupFile = Join-Path $backupDirectory "qizhi-before-reset-$timestamp.dump"
    $containerId = (& docker compose ps -q db | Select-Object -First 1)
    if (-not $containerId) {
        throw "数据库容器未运行，无法创建安全备份。"
    }

    Write-Step "正在备份当前数据库"
    & docker exec $containerId sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/qizhi-before-reset.dump' | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "数据库备份失败，已取消重置。"
    }
    & docker cp "${containerId}:/tmp/qizhi-before-reset.dump" $backupFile | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "备份文件复制失败，已取消重置。"
    }
    & docker exec $containerId rm -f /tmp/qizhi-before-reset.dump | Out-Host
    Write-Success "当前数据已备份到：$backupFile"
    return $backupFile
}

function Test-PlatformHealth {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 4
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Test-ServiceHealthy {
    param([string]$Service)
    $containerId = (& docker compose ps -q $Service 2>$null | Select-Object -First 1)
    if (-not $containerId) {
        return $false
    }
    $state = (& docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $containerId 2>$null)
    return $state -in @("healthy", "running")
}

function Wait-ForPlatform {
    Write-Step "正在等待数据库、调度服务和页面准备完成"
    for ($attempt = 1; $attempt -le 90; $attempt++) {
        if (
            (Test-PlatformHealth) -and
            (Test-ServiceHealthy "frontend") -and
            (Test-ServiceHealthy "worker")
        ) {
            Write-Success "全部服务已经就绪"
            return $true
        }
        if ($attempt % 5 -eq 0) {
            Write-Host "  服务仍在初始化（$($attempt * 2) 秒）..."
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Show-PlatformStatus {
    Write-Host ""
    & docker compose ps
    Write-Host ""
    if (Test-PlatformHealth) {
        Write-Success "平台运行正常：$appUrl"
        return
    }
    Write-Failure "平台尚未就绪"
}

function Start-Platform {
    Write-Title "祁智运平台 · 一键启动"
    Ensure-Docker
    Ensure-EnvironmentFile
    Set-Location -LiteralPath $projectRoot

    Write-Step "正在启动平台；第一次运行需要下载基础镜像，请保持网络连接"
    & docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "容器构建或启动失败。"
    }

    if (-not (Wait-ForPlatform)) {
        Write-Failure "等待服务就绪超时，下面显示当前状态和最近日志："
        & docker compose ps
        & docker compose logs --tail 40 api frontend db redis
        throw "平台未能正常启动，请把此窗口截图交给维护人员。"
    }

    Show-PlatformStatus
    Write-Host ""
    Write-Host "管理员账号：admin" -ForegroundColor Yellow
    Write-Host "管理员密码：QizhiDemo2026!" -ForegroundColor Yellow
    Write-Host "驾驶员账号：driver"
    Write-Host "驾驶员密码：DriverDemo2026!"
    Write-Host ""
    if (-not $NoPause) {
        Write-Host "正在打开浏览器..." -ForegroundColor Cyan
        Start-Process $appUrl
    }
}

function Stop-Platform {
    Write-Title "祁智运平台 · 安全停止"
    Ensure-Docker
    Set-Location -LiteralPath $projectRoot
    Write-Step "正在停止平台，业务数据会继续保留"
    & docker compose stop
    if ($LASTEXITCODE -ne 0) {
        throw "平台停止失败。"
    }
    Write-Success "平台已停止，数据库和配置数据均已保留"
}

function Check-Platform {
    Write-Title "祁智运平台 · 状态检查"
    Ensure-Docker
    Set-Location -LiteralPath $projectRoot
    Show-PlatformStatus
}

function Reset-Platform {
    Write-Title "祁智运平台 · 恢复标准演示数据"
    Ensure-Docker
    Ensure-EnvironmentFile
    Set-Location -LiteralPath $projectRoot

    Write-Host "此操作将恢复以下标准状态：" -ForegroundColor Yellow
    Write-Host "  · 18 个县内校准物流节点"
    Write-Host "  · 16 个参考需求演示订单（约 8.3 吨）"
    Write-Host "  · 5 台可用车辆"
    Write-Host "  · 管理员和驾驶员标准账号"
    Write-Host "  · 清空已产生的审批、执行和历史记录"
    Write-Host "  · 将动态事件恢复为初始待处置状态"
    Write-Host ""
    Write-Host "AI Key、高德地图配置和数据质量规则会保留。" -ForegroundColor Green
    Write-Host "重置前会自动备份当前数据库。" -ForegroundColor Green
    Write-Host ""

    if (-not $Force) {
        $confirmation = Read-Host "确认恢复请输入 RESET，取消请直接关闭窗口"
        if ($confirmation -ne "RESET") {
            Write-Host "已取消，没有修改任何数据。" -ForegroundColor Yellow
            return
        }
    }

    Write-Step "正在准备平台服务"
    & docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "平台服务准备失败，未执行重置。"
    }
    if (-not (Wait-ForPlatform)) {
        throw "平台服务未能就绪，未执行重置。"
    }

    $backupFile = Backup-Database

    Write-Step "正在暂停业务服务"
    & docker compose stop frontend worker api
    if ($LASTEXITCODE -ne 0) {
        throw "业务服务暂停失败，未执行重置。"
    }

    Write-Step "正在恢复标准场景和业务状态"
    & docker compose run --rm --no-deps api python -m app.demo_reset
    if ($LASTEXITCODE -ne 0) {
        throw "演示数据恢复失败；原数据库备份位于 $backupFile"
    }

    Write-Step "正在重新启动平台"
    & docker compose up -d api worker frontend
    if ($LASTEXITCODE -ne 0) {
        throw "数据已恢复，但服务重新启动失败。"
    }
    if (-not (Wait-ForPlatform)) {
        throw "数据已恢复，但服务未能在规定时间内就绪。"
    }

    Write-Success "标准演示数据已经恢复"
    Write-Host "备份文件：$backupFile"
    Write-Host "管理员：admin / QizhiDemo2026!"
    Write-Host "驾驶员：driver / DriverDemo2026!"
    if (-not $NoPause) {
        Write-Host ""
        Write-Host "正在打开全新的登录页面..." -ForegroundColor Cyan
        Start-Process "$appUrl/overview?demo_reset=1"
    }
}

try {
    switch ($Action) {
        "Start" { Start-Platform }
        "Stop" { Stop-Platform }
        "Status" { Check-Platform }
        "Reset" { Reset-Platform }
    }
}
catch {
    Write-Host ""
    Write-Failure $_.Exception.Message
    Write-Host "如果仍无法启动，请运行【检查平台状态.bat】并把窗口截图发给维护人员。" -ForegroundColor Yellow
    Wait-ForExit
    exit 1
}

Wait-ForExit
