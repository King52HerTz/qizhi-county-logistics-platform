$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$projectRoot = Split-Path -Parent $PSScriptRoot
$appUrl = "http://127.0.0.1:80"
$healthUrl = "$appUrl/api/v1/health/ready"
$cloudflaredDownload = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
$stateDirectory = Join-Path $env:LOCALAPPDATA "QizhiYun"
$toolDirectory = Join-Path $stateDirectory "tools"
$logDirectory = Join-Path $stateDirectory "logs"
$pidFile = Join-Path $stateDirectory "cloudflared.pid"
$cloudflaredPath = $null
$tunnelProcess = $null
$stdoutLog = $null
$stderrLog = $null

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

function Test-DockerEngine {
    & docker info --format "{{.ServerVersion}}" *> $null
    return $LASTEXITCODE -eq 0
}

function Find-DockerDesktop {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "未检测到 Docker Desktop。请先双击【安装并启动祁智运平台.bat】完成首次安装。"
    }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose 不可用，请先启动或更新 Docker Desktop。"
    }
    if (-not (Test-DockerEngine)) {
        $dockerDesktop = Find-DockerDesktop
        if (-not $dockerDesktop) {
            throw "已安装 Docker 命令，但未找到 Docker Desktop，请手动启动后重试。"
        }
        Write-Step "正在自动启动 Docker Desktop"
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
        for ($attempt = 1; $attempt -le 60; $attempt++) {
            Start-Sleep -Seconds 2
            if (Test-DockerEngine) {
                Write-Success "Docker Desktop 已就绪"
                return
            }
            if ($attempt % 10 -eq 0) {
                Write-Host "  仍在等待 Docker Desktop（约 $($attempt * 2) 秒）..."
            }
        }
        throw "Docker Desktop 启动超时，请确认它已正常运行后重试。"
    }
    Write-Success "Docker Desktop 已运行"
}

function Ensure-Platform {
    Set-Location -LiteralPath $projectRoot
    Write-Step "正在启动并检查祁智运平台"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker compose up -d --no-build *> $null
    $composeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($composeExitCode -ne 0) {
        throw "平台镜像尚未准备好，请先双击【启动祁智运平台.bat】完成首次启动后再分享。"
    }
    for ($attempt = 1; $attempt -le 45; $attempt++) {
        if (Test-PlatformHealth) {
            Write-Success "平台已经就绪"
            return
        }
        if ($attempt % 10 -eq 0) {
            Write-Host "  正在等待平台服务（约 $attempt 秒）..."
        }
        Start-Sleep -Seconds 1
    }
    throw "平台启动超时，请先双击【检查平台状态.bat】确认服务正常。"
}

function Test-PlatformHealth {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Get-CloudflaredPath {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command -and $command.Path) {
        return $command.Path
    }

    $localPath = Join-Path $toolDirectory "cloudflared.exe"
    if (Test-Path -LiteralPath $localPath) {
        return $localPath
    }
    return $null
}

function Ensure-Cloudflared {
    $existingPath = Get-CloudflaredPath
    if ($existingPath) {
        return $existingPath
    }

    if (-not (Test-Path -LiteralPath $toolDirectory)) {
        New-Item -ItemType Directory -Path $toolDirectory -Force | Out-Null
    }

    $downloadPath = Join-Path $toolDirectory "cloudflared.download"
    $targetPath = Join-Path $toolDirectory "cloudflared.exe"
    Write-Step "首次分享需要下载 Cloudflare 连接组件（约几 MB）"
    try {
        Invoke-WebRequest -Uri $cloudflaredDownload -OutFile $downloadPath -UseBasicParsing
        $downloaded = Get-Item -LiteralPath $downloadPath
        if ($downloaded.Length -lt 1MB) {
            throw "下载文件大小异常"
        }
        Move-Item -LiteralPath $downloadPath -Destination $targetPath -Force
    }
    catch {
        Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue
        throw "Cloudflare 连接组件下载失败。可从官方页面手动下载后重试：https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
    }

    & $targetPath --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $targetPath -Force -ErrorAction SilentlyContinue
        throw "Cloudflare 连接组件无法运行，请重新下载后重试。"
    }
    Write-Success "Cloudflare 连接组件已准备好"
    return $targetPath
}

function Read-TunnelOutput {
    $content = @()
    foreach ($path in @($stdoutLog, $stderrLog)) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            $content += Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
        }
    }
    return ($content -join "`n")
}

function Start-ShareTunnel {
    if (-not (Test-Path -LiteralPath $logDirectory)) {
        New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdoutLog = Join-Path $logDirectory "cloudflared-$stamp.out.log"
    $stderrLog = Join-Path $logDirectory "cloudflared-$stamp.err.log"
    $tunnelProcess = Start-Process -FilePath $cloudflaredPath `
        -ArgumentList @("tunnel", "--protocol", "http2", "--url", $appUrl) `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $pidFile -Value ([string]$tunnelProcess.Id) -Encoding ascii

    for ($attempt = 1; $attempt -le 45; $attempt++) {
        Start-Sleep -Seconds 1
        if ($tunnelProcess.HasExited) {
            $details = Read-TunnelOutput
            if ($details.Length -gt 600) {
                $details = $details.Substring($details.Length - 600)
            }
            throw "公网分享连接启动失败。$details"
        }
        $output = Read-TunnelOutput
        $match = [regex]::Match($output, "https://[a-z0-9-]+\.trycloudflare\.com")
        $registered = $output -match "Registered tunnel connection"
        if ($match.Success -and $registered) {
            return $match.Value
        }
        if ($attempt % 10 -eq 0) {
            Write-Host "  正在连接公网分享服务（约 $attempt 秒，等待连接注册）..."
        }
    }
    throw "公网分享连接注册超时。当前网络可能无法通过 HTTP/2 连接 Cloudflare，请检查网络或稍后重试。"
}

function Test-PublicUrl {
    param([string]$Url)
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 12
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return $true
            }
        }
        catch {
            $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
            if ($curl) {
                $previousErrorActionPreference = $ErrorActionPreference
                $ErrorActionPreference = "Continue"
                $statusCode = & $curl.Path -L -sS --max-time 12 -o NUL -w "%{http_code}" $Url 2>$null
                $curlExitCode = $LASTEXITCODE
                $ErrorActionPreference = $previousErrorActionPreference
                if ($curlExitCode -eq 0 -and [string]$statusCode -match "^[23]\d\d$") {
                    return $true
                }
            }
        }
        if ($attempt -lt 3) {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

function Stop-ShareTunnel {
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $pidFile) {
        $savedPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($savedPid -match '^\d+$') {
            $savedProcess = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
            if ($savedProcess -and $savedProcess.ProcessName -eq "cloudflared") {
                Stop-Process -Id $savedProcess.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
}

try {
    Write-Title "祁智运平台 · 分享给同学"
    Ensure-Docker
    Ensure-Platform
    if (-not (Test-PlatformHealth)) {
        throw "平台尚未就绪，请先双击【检查平台状态.bat】确认服务正常。"
    }

    $cloudflaredPath = Ensure-Cloudflared
    Write-Step "正在生成公网分享地址"
    $publicUrl = Start-ShareTunnel
    $reachable = Test-PublicUrl -Url $publicUrl

    Write-Host ""
    Write-Host "同学访问地址：" -ForegroundColor Green
    Write-Host $publicUrl -ForegroundColor Yellow
    Write-Host ""
    if ($reachable) {
        Write-Success "公网地址已确认可以访问"
    }
    else {
        Write-Host "[提示] 地址已生成，但本机暂时无法回访；请直接让同学打开测试。" -ForegroundColor Yellow
    }
    try {
        Set-Clipboard -Value $publicUrl
        Write-Host "访问地址已复制到剪贴板。"
    }
    catch { }
    Write-Host ""
    Write-Host "请保持 Docker Desktop、此窗口和电脑网络连接。" -ForegroundColor Cyan
    Write-Host "同学看完后按 Enter 结束分享；也可双击【停止分享链接.bat】。" -ForegroundColor Cyan
    Write-Host "临时分享链接会自动使用免白名单的县域运营地图，无需修改高德配置。" -ForegroundColor DarkYellow
    Write-Host "如需在公网展示高德道路底图，请改用固定域名，并只在高德控制台配置一次该域名。" -ForegroundColor DarkYellow
    Write-Host ""
    [void](Read-Host "按 Enter 结束本次分享")
}
catch {
    Write-Host ""
    Write-Failure $_.Exception.Message
    Write-Host ""
    [void](Read-Host "按 Enter 关闭此窗口")
    exit 1
}
finally {
    Stop-ShareTunnel
}
