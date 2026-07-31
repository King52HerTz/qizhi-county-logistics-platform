param(
    [string]$BaseUrl = "http://localhost/api/v1",
    [string]$Username = $(if ($env:ADMIN_USERNAME) { $env:ADMIN_USERNAME } else { "admin" }),
    [string]$Password = $(if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { "QizhiDemo2026!" }),
    [switch]$SkipDocker,
    [switch]$StrictSecurity
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$results = [System.Collections.Generic.List[object]]::new()

function Add-Result {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $results.Add([pscustomobject]@{
        Check = $Name
        Status = $(if ($Passed) { "PASS" } else { "FAIL" })
        Detail = $Detail
    })
}

try {
    $live = Invoke-RestMethod "$BaseUrl/health/live"
    Add-Result "API liveness" ($live.status -eq "ok") "version $($live.version)"
} catch {
    Add-Result "API liveness" $false $_.Exception.Message
}

try {
    $ready = Invoke-RestMethod "$BaseUrl/health/ready"
    $readyPassed = $ready.checks.database -and $ready.checks.redis -and $ready.checks.migrations
    Add-Result "API readiness" $readyPassed (($ready.checks | ConvertTo-Json -Compress))
} catch {
    Add-Result "API readiness" $false $_.Exception.Message
}

$headers = @{}
try {
    $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" `
        -ContentType "application/json" `
        -Body (@{ username = $Username; password = $Password } | ConvertTo-Json)
    $headers.Authorization = "Bearer $($login.access_token)"
    Add-Result "Authentication" ([bool]$login.access_token) "role $($login.role)"
} catch {
    Add-Result "Authentication" $false $_.Exception.Message
}

if ($headers.Authorization) {
    try {
        $operations = Invoke-RestMethod -Headers $headers "$BaseUrl/operations/readiness"
        Add-Result "Operations readiness" ($operations.overall_score -ge 0) "score $($operations.overall_score)/100"
    } catch {
        Add-Result "Operations readiness" $false $_.Exception.Message
    }

    try {
        $spatial = Invoke-RestMethod -Headers $headers "$BaseUrl/scenario/spatial-status"
        $detail = if ($spatial.aligned) {
            "coordinate snapshot aligned"
        } else {
            "$($spatial.missing_node_ids.Count) nodes require republish; $($spatial.unverified_node_ids.Count) nodes require verification"
        }
        Add-Result "Spatial governance" $true $detail
    } catch {
        Add-Result "Spatial governance" $false $_.Exception.Message
    }
}

try {
    $openapi = Invoke-RestMethod "$BaseUrl/openapi.json"
    $legacyVisible = [bool]$openapi.paths.PSObject.Properties["/api/v1/competition/readiness"]
    Add-Result "Professional API surface" (-not $legacyVisible) "legacy paths hidden from OpenAPI"
} catch {
    Add-Result "Professional API surface" $false $_.Exception.Message
}

if (-not $SkipDocker) {
    try {
        $running = @(docker compose ps --status running --services)
        $expected = @("api", "db", "frontend", "redis", "worker")
        $missing = @($expected | Where-Object { $_ -notin $running })
        Add-Result "Docker services" ($missing.Count -eq 0) `
            $(if ($missing.Count) { "missing: $($missing -join ', ')" } else { "all runtime services running" })
    } catch {
        Add-Result "Docker services" $false $_.Exception.Message
    }
}

$usingDefaultPassword = $Password -eq "QizhiDemo2026!"
if ($StrictSecurity) {
    Add-Result "Production credentials" (-not $usingDefaultPassword) `
        $(if ($usingDefaultPassword) { "default administrator password must be changed" } else { "custom administrator password configured" })
} elseif ($usingDefaultPassword) {
    $results.Add([pscustomobject]@{
        Check = "Production credentials"
        Status = "WARN"
        Detail = "local default password is active; use -StrictSecurity before production delivery"
    })
}

$results | Format-Table -AutoSize
if ($results.Status -contains "FAIL") {
    exit 1
}
