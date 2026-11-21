#Requires -Version 5.1
<#
.SYNOPSIS
  Install and test the six AssetFlow addons inside the Docker Compose Odoo service.

.DESCRIPTION
  Installs the addons in dependency order (ADR-0001), then runs each addon's test suite with
  --test-enable. Stops at the first failed command or failed test. Logs are written to
  odoo-data/logs/ (git-ignored).

  Preconditions: Docker Desktop is running and `docker compose up -d` has been done. The database
  is created on first install if it does not exist.

.PARAMETER Database
  Odoo database name. Default: assetflow.

.PARAMETER Addon
  Only install and test this addon (its dependencies are installed by Odoo). Default: all six.

.PARAMETER SkipInstall
  Skip the install pass and only run the tests. Use when nothing changed since the last install.

.EXAMPLE
  ./scripts/test.ps1

.EXAMPLE
  ./scripts/test.ps1 -Addon assetflow_booking -SkipInstall
#>
[CmdletBinding()]
param(
    [string]$Database = "assetflow",
    [string]$Addon,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot "docker-compose.yml"
$logDir = Join-Path $repoRoot "odoo-data/logs"

# ADR-0001: one-directional dependencies, so this order is the install order.
$dependencyOrder = @(
    "assetflow_base",
    "assetflow_assets",
    "assetflow_booking",
    "assetflow_maintenance",
    "assetflow_audit",
    "assetflow_reports"
)

if (-not (Test-Path $composeFile)) {
    throw "docker-compose.yml not found at $composeFile"
}

if ($Addon) {
    if ($dependencyOrder -notcontains $Addon) {
        throw "Unknown addon '$Addon'. Expected one of: $($dependencyOrder -join ', ')"
    }
    $targets = @($Addon)
}
else {
    $targets = $dependencyOrder
}

# Fail early with a readable message rather than an Odoo "module not found" traceback.
$missing = @()
foreach ($target in $targets) {
    $manifest = Join-Path $repoRoot (Join-Path $target "__manifest__.py")
    if (-not (Test-Path $manifest)) {
        $missing += $target
    }
}
if ($missing.Count -gt 0) {
    throw ("Addon folder(s) without __manifest__.py: {0}. They do not exist on this branch yet; " +
        "run this script on a branch that contains the addon code.") -f ($missing -join ", ")
}

# The engine and the services must be up before `docker compose exec` works.
$serverVersion = $null
try {
    $serverVersion = & docker info --format '{{.ServerVersion}}' 2>$null
}
catch {
    $serverVersion = $null
}
if (-not $serverVersion) {
    throw ("The Docker engine is not running. Start Docker Desktop, wait for 'Engine running', " +
        "then run: docker compose up -d")
}

$running = @()
$psOk = $true
try {
    $running = @(& docker compose --file $composeFile ps --status running --services 2>$null)
}
catch {
    $psOk = $false
}
if (-not $psOk) {
    throw "docker compose ps failed while checking the stack. Is Docker Desktop healthy?"
}
if ($running -notcontains "odoo") {
    throw "The odoo service is not running. Start the stack with: docker compose up -d"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$script:results = @()

function Write-Summary {
    Write-Host ""
    Write-Host "Summary"
    foreach ($result in $script:results) {
        Write-Host ("  {0,-5} {1}" -f $result.Result, $result.Step)
    }
}

function Invoke-Odoo {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$OdooArgs
    )

    $logFile = Join-Path $logDir ("{0}-{1}.log" -f $Label, (Get-Date -Format "yyyyMMdd-HHmmss"))
    Write-Host ""
    Write-Host "==> $Label"
    Write-Host "    odoo $($OdooArgs -join ' ')"
    Write-Host "    log: $logFile"

    # Windows PowerShell turns native stderr into decorated error records and can abort on an Odoo
    # WARNING. Let cmd.exe merge the streams, so the log is plain text and the exit code survives.
    $quotedArgs = @($OdooArgs | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
        })
    $commandLine = 'docker compose --file "{0}" exec -T odoo /entrypoint.sh odoo {1} 2>&1' -f `
        $composeFile, ($quotedArgs -join ' ')

    & cmd.exe /d /c $commandLine | Tee-Object -FilePath $logFile
    $exitCode = $LASTEXITCODE

    $log = Get-Content -Path $logFile -Raw
    if (-not $log) { $log = "" }
    $testFailures = [regex]::Matches($log, "(?m)\b(FAIL|ERROR):\s").Count
    $tracebacks = [regex]::Matches($log, "(?m)^Traceback \(most recent call last\)").Count

    if ($exitCode -ne 0 -or $testFailures -gt 0 -or $tracebacks -gt 0) {
        $script:results += [pscustomobject]@{ Step = $Label; Result = "FAIL" }
        Write-Host ""
        Write-Host "FAILED: $Label (exit $exitCode, failure lines $testFailures, tracebacks $tracebacks)" -ForegroundColor Red
        Write-Host "Log: $logFile" -ForegroundColor Red
        Write-Summary
        exit 1
    }

    # Odoo 19 prints one stats line per tested module; surface it so the summary is evidence, not a claim.
    $stats = [regex]::Matches($log, "(?m)^.*odoo\.tests\.stats:\s*(.+)$")
    foreach ($match in $stats) {
        Write-Host "    tests: $($match.Groups[1].Value.Trim())"
    }

    $script:results += [pscustomobject]@{ Step = $Label; Result = "PASS" }
    Write-Host "ok: $Label"
}

if (-not $SkipInstall) {
    Invoke-Odoo -Label "install" -OdooArgs @(
        "-d", $Database,
        "-i", ($targets -join ","),
        "--without-demo",
        "--no-http",
        "--http-port=8079",
        "--stop-after-init"
    )
}

foreach ($target in $targets) {
    Invoke-Odoo -Label "test-$target" -OdooArgs @(
        "-d", $Database,
        "-u", $target,
        "--test-enable",
        "--test-tags", "/$target",
        "--no-http",
        "--http-port=8079",
        "--stop-after-init"
    )
}

Write-Summary
Write-Host ""
Write-Host "All requested addons installed and tested: $($targets -join ', ')" -ForegroundColor Green
Write-Host "Logs: $logDir"
