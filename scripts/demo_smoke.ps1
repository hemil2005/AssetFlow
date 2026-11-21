#Requires -Version 5.1
<#
.SYNOPSIS
  Release-gate smoke test: build the demo on a throwaway database and prove the seed and
  narrative both completed.

.DESCRIPTION
  Thin wrapper around scripts/demo.ps1, so the drop/create/install/seed logic lives in one place.
  It runs the demo with -NoServe (no restart, no HTTP wait), then asserts the evidence in the
  generated logs:

    - scripts/seed_demo.py printed the KPI block and "demo seed complete" (the seed also
      asserts the KPI values themselves and a real login);
    - scripts/demo_narrative.py printed "demo narrative complete";
    - neither log contains a traceback or CRITICAL.

  The database is dropped and recreated on every run, so it is disposable by design. The default
  name matches the demo script's safe pattern (^assetflow_(demo|seed|test)).

.PARAMETER Database
  Throwaway database name. Default: assetflow_test_smoke.

.PARAMETER Port
  Forwarded to demo.ps1 for its printed URL; unused with -NoServe. Default: 8069.

.PARAMETER Password
  Password for the seeded demo users. Defaults to demo.ps1's rules
  ($env:ASSETFLOW_DEMO_PASSWORD, then AssetFlow!2026). Never printed.

.EXAMPLE
  ./scripts/demo_smoke.ps1

.EXAMPLE
  ./scripts/demo_smoke.ps1 -Database assetflow_test_release
#>
[CmdletBinding()]
param(
    [string]$Database = "assetflow_test_smoke",
    [ValidateRange(1, 65535)][int]$Port = 8069,
    [string]$Password
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$demoScript = Join-Path $PSScriptRoot "demo.ps1"
$logDir = Join-Path $repoRoot "odoo-data/logs"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ""
    Write-Host "DEMO SMOKE FAIL" -ForegroundColor Red
    Write-Host "  $Message"
    exit 1
}

function Assert-LogContains {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $text = Get-Content -Path $Path -Raw
    if (-not $text -or -not $text.Contains($Pattern)) {
        Fail "$Label missing '$Pattern' in $Path"
    }
}

function Assert-LogClean {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $text = Get-Content -Path $Path -Raw
    if ($text -match "(?m)^Traceback \(most recent call last\)") {
        Fail "$Label raised a Python traceback in $Path"
    }
    if ($text -match "(?m)\bCRITICAL\b") {
        Fail "$Label logged CRITICAL in $Path"
    }
}

if (-not (Test-Path $demoScript)) {
    Fail "scripts/demo.ps1 not found at $demoScript"
}

$startedAt = Get-Date
Write-Host ""
Write-Host "==> Demo smoke gate on '$Database'" -ForegroundColor Cyan

$demoArguments = @{
    Database  = $Database
    Port      = $Port
    NoServe   = $true
}
if ($Password) {
    $demoArguments.Password = $Password
}

try {
    & $demoScript @demoArguments
    if (-not $?) {
        Fail "demo.ps1 reported failure; read the log above."
    }
}
catch {
    Fail "demo.ps1 failed: $($_.Exception.Message)"
}

function Get-RunLog {
    param([Parameter(Mandatory = $true)][string]$Label)
    $log = Get-ChildItem -Path $logDir -Filter ("{0}-*.log" -f $Label) -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $startedAt } |
        Sort-Object LastWriteTime |
        Select-Object -Last 1
    if (-not $log) {
        Fail "No $Label log written by this run under $logDir"
    }
    return $log.FullName
}

$seedLog = Get-RunLog "seed"
$narrativeLog = Get-RunLog "narrative"

Assert-LogClean -Path $seedLog -Label "Demo seed"
Assert-LogClean -Path $narrativeLog -Label "Demo narrative"
Assert-LogContains -Path $seedLog -Pattern "=== AssetFlow demo KPIs ===" -Label "Demo seed"
Assert-LogContains -Path $seedLog -Pattern "demo seed complete" -Label "Demo seed"
Assert-LogContains -Path $narrativeLog -Pattern "demo narrative complete" -Label "Demo narrative"

Write-Host ""
Write-Host "DEMO SMOKE PASS" -ForegroundColor Green
Write-Host "  Database:  $Database"
Write-Host "  Seed:      $seedLog"
Write-Host "  Narrative: $narrativeLog"
Write-Host "  Assertions: KPI block, seed marker, narrative marker, no traceback/CRITICAL"
exit 0
