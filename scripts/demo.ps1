#Requires -Version 5.1
<#
.SYNOPSIS
  Build a fresh, seeded AssetFlow demo database and serve it, in one command.

.DESCRIPTION
  Drops and recreates a throwaway database in the local Docker Compose Odoo 19 stack, installs the
  six addons, runs the demo seed (and, unless skipped, the demo narrative) through `odoo shell`,
  restarts Odoo, and prints the URL and the six demo logins.

  This script destroys the target database. By default it only accepts a name matching
  ^assetflow_(demo|seed|test); anything else needs -Force. Never point it at production.

  `odoo shell` rolls back its transaction on exit, so the wrapper appends an explicit
  `env.cr.commit()` after the piped script. The Postgres password is never read, printed, or placed
  on a command line: the db container is reached over its local socket (trust auth).

  See docs/instructions/demo-runbook.md for the demo order and troubleshooting.

.PARAMETER Database
  Database to drop, recreate, install into, and seed. Default: assetflow_demo.

.PARAMETER Port
  Host port used in the printed URL. Default: 8069, matching docker-compose.yml. If the compose
  file publishes a different host port, that port is used instead and a warning is printed.

.PARAMETER Password
  Password applied to the five seeded demo users. Defaults to $env:ASSETFLOW_DEMO_PASSWORD, then to
  AssetFlow!2026. It is passed to the seed process only; it is never printed.

.PARAMETER SkipSeed
  Install the addons but do not run scripts/seed_demo.py.

.PARAMETER SkipNarrative
  Do not run scripts/demo_narrative.py.

.PARAMETER Force
  Allow dropping a database whose name does not match ^assetflow_(demo|seed|test).

.EXAMPLE
  ./scripts/demo.ps1

.EXAMPLE
  $env:ASSETFLOW_DEMO_PASSWORD = 'LocalOnly!42'
  ./scripts/demo.ps1 -Database assetflow_demo -Port 8069

.EXAMPLE
  ./scripts/demo.ps1 -SkipSeed -SkipNarrative
#>
[CmdletBinding()]
param(
    [string]$Database = "assetflow_demo",
    [ValidateRange(1, 65535)][int]$Port = 8069,
    [string]$Password = $(if ($env:ASSETFLOW_DEMO_PASSWORD) { $env:ASSETFLOW_DEMO_PASSWORD } else { "AssetFlow!2026" }),
    [switch]$SkipSeed,
    [switch]$SkipNarrative,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$global:LASTEXITCODE = 0

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot "docker-compose.yml"
$envFile = Join-Path $repoRoot ".env"
$envExample = Join-Path $repoRoot ".env.example"
$seedScript = Join-Path $repoRoot "scripts/seed_demo.py"
$narrativeScript = Join-Path $repoRoot "scripts/demo_narrative.py"
$logDir = Join-Path $repoRoot "odoo-data/logs"

# ADR-0001: one-directional dependencies, so this order is the install order.
$addonOrder = @(
    "assetflow_base",
    "assetflow_assets",
    "assetflow_booking",
    "assetflow_maintenance",
    "assetflow_audit",
    "assetflow_reports"
)
$addonsCsv = $addonOrder -join ","

# --- Preconditions ----------------------------------------------------------

if (-not (Test-Path $composeFile)) {
    throw "docker-compose.yml not found at $composeFile. Run this from a checkout of the repo."
}

if ([string]::IsNullOrWhiteSpace($Password)) {
    throw "The demo password is empty. Pass -Password or set ASSETFLOW_DEMO_PASSWORD."
}
if ($Password -match "[\r\n]") {
    throw "The demo password must be a single line."
}

# Guard the destructive step before doing any Docker work.
if ($Database -notmatch '^[A-Za-z0-9_]+$') {
    throw "Invalid database name '$Database'. Use letters, digits, and underscores only."
}
if ($Database -notmatch '^assetflow_(demo|seed|test)') {
    if (-not $Force) {
        throw ("Refusing to drop database '$Database': the name does not match ^assetflow_(demo|seed|test). " +
            "Use the default -Database assetflow_demo, or pass -Force if you really mean to destroy it.")
    }
    Write-Warning "Dropping non-standard database '$Database' because -Force was given."
}

# Fail early with a readable message rather than an Odoo "module not found" traceback.
$missingAddons = @()
foreach ($addon in $addonOrder) {
    $manifest = Join-Path $repoRoot (Join-Path $addon "__manifest__.py")
    if (-not (Test-Path $manifest)) {
        $missingAddons += $addon
    }
}
if ($missingAddons.Count -gt 0) {
    $message = ("Addon folder(s) without __manifest__.py: {0}. They are not on this branch yet; check out " +
        "a branch that contains the addon code (for example feat/assetflow-demo) before running the demo.") -f `
        ($missingAddons -join ", ")
    throw $message
}

if (-not $SkipSeed -and -not (Test-Path $seedScript)) {
    throw ("scripts/seed_demo.py not found. It lives on the demo feature branch; check it out, or pass " +
        "-SkipSeed to install only.")
}
if (-not $SkipNarrative -and -not (Test-Path $narrativeScript)) {
    throw ("scripts/demo_narrative.py not found. It lives on the demo feature branch; check it out, or " +
        "pass -SkipNarrative to run the seed only.")
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw ("docker was not found on PATH. Install Docker Desktop for Windows, open a new terminal, and " +
        "check: docker compose version")
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# --- Helpers ----------------------------------------------------------------

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function New-LogPath {
    param([Parameter(Mandatory = $true)][string]$Label)
    return (Join-Path $logDir ("{0}-{1}.log" -f $Label, (Get-Date -Format "yyyyMMdd-HHmmss")))
}

function ConvertTo-LogLine {
    # Windows PowerShell turns native stderr into ErrorRecords; flatten them so logs stay plain text.
    param([Parameter(ValueFromPipeline = $true)]$InputObject)
    process {
        if ($InputObject -is [System.Management.Automation.ErrorRecord]) {
            $message = $InputObject.Exception.Message
            if ($message) {
                return $message.TrimEnd()
            }
            return $InputObject.ToString().TrimEnd()
        }
        return $InputObject
    }
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogFile
    )

    # A native command writing to stderr must not abort the script on a warning line.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments 2>&1 | ConvertTo-LogLine | Tee-Object -FilePath $LogFile | Out-Host
        return $global:LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Invoke-LoggedOdooShell {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string]$LogFile
    )

    Write-Step ("{0}: {1}" -f $Label, (Split-Path -Leaf $ScriptPath))
    Write-Host "    log: $LogFile"

    $source = Get-Content -Path $ScriptPath -Raw
    if (-not $source) {
        throw "The script $ScriptPath is empty."
    }

    # odoo shell calls cr.rollback() after reading stdin, so commit explicitly or the demo data
    # disappears when the process exits.
    $source = $source.TrimEnd() + "`n`nenv.cr.commit()`n"

    $previousErrorAction = $ErrorActionPreference
    $previousEncoding = $OutputEncoding
    $ErrorActionPreference = "Continue"
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $shellArguments = @(
        "compose", "--file", $composeFile, "exec", "-T",
        # The value is never echoed. shell only; install/db commands carry no secrets.
        "-e", "ASSETFLOW_DEMO_PASSWORD=$Password",
        "odoo", "/entrypoint.sh", "odoo", "shell",
        "--database", $Database, "--no-http", "--log-level=warn"
    )
    try {
        $source | & docker @shellArguments 2>&1 | ConvertTo-LogLine | Tee-Object -FilePath $LogFile | Out-Host
        return $global:LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
        $OutputEncoding = $previousEncoding
    }
}

function Assert-LogClean {
    param(
        [Parameter(Mandatory = $true)][string]$LogFile,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $text = Get-Content -Path $LogFile -Raw
    if (-not $text) {
        # Warnings-only output can be empty; the exit code and the caller's marker check still apply.
        return
    }
    if ($text -match "(?m)^Traceback \(most recent call last\)") {
        throw "$Label raised a Python traceback. Read $LogFile."
    }
    if ($text -match "(?m)\bCRITICAL\b") {
        throw "$Label logged a CRITICAL error. Read $LogFile."
    }
}

function Assert-LogContains {
    param(
        [Parameter(Mandatory = $true)][string]$LogFile,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $text = Get-Content -Path $LogFile -Raw
    if (-not $text -or -not $text.Contains($Pattern)) {
        throw ("$Label finished without printing '$Pattern'; the data may be incomplete. " +
            "Read $LogFile.")
    }
}

function Test-DockerReady {
    # Returns $null when ready, otherwise "engine" or "compose".
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $serverVersion = & docker info --format '{{.ServerVersion}}' 2>$null
        if ($global:LASTEXITCODE -ne 0 -or -not $serverVersion) {
            return "engine"
        }
        $composeVersion = & docker compose version --short 2>$null
        if ($global:LASTEXITCODE -ne 0 -or -not $composeVersion) {
            return "compose"
        }
        return $null
    }
    catch {
        return "engine"
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Read-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Default
    )

    if (-not (Test-Path $Path)) {
        return $Default
    }
    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }
        $name = $trimmed.Substring(0, $separator).Trim()
        if ($name -ne $Key) {
            continue
        }
        $value = $trimmed.Substring($separator + 1).Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        if ($value) {
            return $value
        }
    }
    return $Default
}

function Test-PostgresReady {
    param([Parameter(Mandatory = $true)][string]$DbUser)

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & docker compose --file $composeFile exec -T db pg_isready -U $DbUser -d postgres *> $null
        return ($global:LASTEXITCODE -eq 0)
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Wait-ForPostgres {
    param(
        [Parameter(Mandatory = $true)][string]$DbUser,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PostgresReady -DbUser $DbUser) {
            return
        }
        Start-Sleep -Seconds 2
    }
    throw ("PostgreSQL did not become ready within $TimeoutSeconds seconds. " +
        "Check: docker compose logs db")
}

function Get-PublishedOdooPort {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $line = & docker compose --file $composeFile port odoo 8069 2>$null
        if ($global:LASTEXITCODE -ne 0 -or -not $line) {
            return $null
        }
        $text = (@($line) -join "").Trim()
        $colon = $text.LastIndexOf(":")
        if ($colon -lt 0) {
            return $null
        }
        $portNumber = 0
        if ([int]::TryParse($text.Substring($colon + 1), [ref]$portNumber)) {
            return $portNumber
        }
        return $null
    }
    catch {
        return $null
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Wait-ForHttp {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 120
    )

    $previousProgress = $ProgressPreference
    $ProgressPreference = "SilentlyContinue"
    try {
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        while ((Get-Date) -lt $deadline) {
            try {
                $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
                if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                    return $true
                }
            }
            catch {
                # Not listening yet, or the database selector is mid-redirect: keep waiting.
            }
            Start-Sleep -Seconds 2
        }
        return $false
    }
    finally {
        $ProgressPreference = $previousProgress
    }
}

# --- Docker preflight -------------------------------------------------------

Write-Step "Checking Docker"
$dockerProblem = Test-DockerReady
if ($dockerProblem -eq "engine") {
    throw ("The Docker engine is not running. Start Docker Desktop, wait for 'Engine running', then " +
        "run this script again. (Check: docker info)")
}
if ($dockerProblem -eq "compose") {
    throw ("docker compose is not available. Update Docker Desktop (Compose v2 ships with it) and " +
        "check: docker compose version")
}
Write-Host "    Docker engine and Compose v2 are available."

# --- .env -------------------------------------------------------------------

Write-Step "Checking .env"
if (-not (Test-Path $envFile)) {
    if (-not (Test-Path $envExample)) {
        throw "Neither .env nor .env.example exists at $repoRoot."
    }
    Copy-Item -Path $envExample -Destination $envFile
    Write-Host "    Created .env from .env.example. Edit it if you want a different Postgres password."
}
else {
    Write-Host "    Using the existing .env."
}
# The Postgres password is deliberately neither read nor printed. The official postgres image
# trusts local socket connections, which is all this script uses.
$dbUser = Read-DotEnvValue -Path $envFile -Key "POSTGRES_USER" -Default "odoo"

# --- Stack ------------------------------------------------------------------

Write-Step "Starting the Docker Compose stack"
Write-Host "    The first run pulls images and can take a few minutes."
$upLog = New-LogPath "up"
$upExit = Invoke-LoggedCommand -FilePath "docker" -Arguments @(
    "compose", "--file", $composeFile, "up", "-d"
) -LogFile $upLog
if ($upExit -ne 0) {
    $hint = ""
    $upText = Get-Content -Path $upLog -Raw
    if ($upText -match "port is already allocated|address already in use") {
        $hint = (" Port 8069 is already in use: stop the other process, or change the port mapping in " +
            "docker-compose.yml (see docs/instructions/demo-runbook.md).")
    }
    throw "docker compose up failed (exit $upExit).$hint Log: $upLog"
}

Write-Step "Waiting for PostgreSQL"
Wait-ForPostgres -DbUser $dbUser
Write-Host "    PostgreSQL is ready."

# --- Database ---------------------------------------------------------------

Write-Step "Recreating database '$Database'"
$dropLog = New-LogPath "dropdb"
$dropExit = Invoke-LoggedCommand -FilePath "docker" -Arguments @(
    "compose", "--file", $composeFile, "exec", "-T", "db",
    "dropdb", "--if-exists", "--force", "-U", $dbUser, $Database
) -LogFile $dropLog
if ($dropExit -ne 0) {
    throw ("dropdb failed (exit $dropExit). Is POSTGRES_USER=$dbUser allowed to drop databases? " +
        "If the db volume was created with another user, reset it with 'docker compose down -v' " +
        "(this deletes local data). Log: $dropLog")
}

$createLog = New-LogPath "createdb"
$createExit = Invoke-LoggedCommand -FilePath "docker" -Arguments @(
    "compose", "--file", $composeFile, "exec", "-T", "db",
    "createdb", "-O", $dbUser, $Database
) -LogFile $createLog
if ($createExit -ne 0) {
    throw "createdb failed (exit $createExit). Log: $createLog"
}
Write-Host "    '$Database' is empty and owned by $dbUser."

# --- Install ----------------------------------------------------------------

Write-Step "Installing the six addons (--without-demo --stop-after-init)"
$installLog = New-LogPath "install"
Write-Host "    log: $installLog"
$installExit = Invoke-LoggedCommand -FilePath "docker" -Arguments @(
    "compose", "--file", $composeFile, "exec", "-T", "odoo",
    "/entrypoint.sh", "odoo",
    "--database", $Database,
    "-i", $addonsCsv,
    "--without-demo",
    "--no-http",
    "--stop-after-init"
) -LogFile $installLog
if ($installExit -ne 0) {
    throw "Addon install failed (exit $installExit). Read $installLog."
}
Assert-LogClean -LogFile $installLog -Label "Addon install"
Write-Host "    Installed: $addonsCsv"

# --- Demo data --------------------------------------------------------------

if ($SkipSeed) {
    Write-Host ""
    Write-Host "    Skipping the demo seed (-SkipSeed)."
}
else {
    $seedLog = New-LogPath "seed"
    $seedExit = Invoke-LoggedOdooShell -Label "Seeding demo data" -ScriptPath $seedScript -LogFile $seedLog
    if ($seedExit -ne 0) {
        throw "Demo seed failed (exit $seedExit). Read $seedLog."
    }
    Assert-LogClean -LogFile $seedLog -Label "Demo seed"
    Assert-LogContains -LogFile $seedLog -Pattern "demo seed complete" -Label "Demo seed"
    Write-Host "    Seed committed and its KPI assertions passed."
}

if ($SkipNarrative) {
    if (-not $SkipSeed) {
        Write-Host "    Skipping the demo narrative (-SkipNarrative)."
    }
}
else {
    $narrativeLog = New-LogPath "narrative"
    $narrativeExit = Invoke-LoggedOdooShell -Label "Running demo narrative" -ScriptPath $narrativeScript -LogFile $narrativeLog
    if ($narrativeExit -ne 0) {
        throw "Demo narrative failed (exit $narrativeExit). Read $narrativeLog."
    }
    Assert-LogClean -LogFile $narrativeLog -Label "Demo narrative"
    Write-Host "    Narrative committed."
}

# --- Serve ------------------------------------------------------------------

Write-Step "Restarting Odoo"
$restartLog = New-LogPath "restart"
$restartExit = Invoke-LoggedCommand -FilePath "docker" -Arguments @(
    "compose", "--file", $composeFile, "restart", "odoo"
) -LogFile $restartLog
if ($restartExit -ne 0) {
    throw "docker compose restart odoo failed (exit $restartExit). Log: $restartLog"
}

$effectivePort = $Port
$publishedPort = Get-PublishedOdooPort
if ($publishedPort -and $publishedPort -ne $Port) {
    Write-Warning ("docker-compose.yml publishes Odoo on host port $publishedPort, not $Port. " +
        "Using $publishedPort for the URL; change the port mapping if you need $Port.")
    $effectivePort = $publishedPort
}
$url = "http://localhost:$effectivePort"

Write-Host "    Waiting for Odoo at $url ..."
if (-not (Wait-ForHttp -Url "$url/web/login" -TimeoutSeconds 120)) {
    throw ("Odoo did not answer at $url within 120 seconds. The database was built, but the server is " +
        "not serving it yet. Check: docker compose logs --tail=100 odoo")
}

# --- Summary ----------------------------------------------------------------

$demoLogins = @(
    [pscustomobject]@{ Login = "admin"; Role = "System Admin (organizations, promotion, audit)" },
    [pscustomobject]@{ Login = "maya.manager"; Role = "Asset Manager (assets, approvals)" },
    [pscustomobject]@{ Login = "dev.head"; Role = "Department Head, IT (approvals, bookings)" },
    [pscustomobject]@{ Login = "priya.employee"; Role = "Employee (holder, bookings, requests)" },
    [pscustomobject]@{ Login = "raj.employee"; Role = "Employee (transfer conflict, bookings)" },
    [pscustomobject]@{ Login = "auditor"; Role = "Sam, Auditor (audit cycle lines)" }
)

Write-Host ""
Write-Host "AssetFlow demo is ready." -ForegroundColor Green
Write-Host "  Database: $Database"
Write-Host "  URL:      $url"
Write-Host ""
Write-Host "Log in as:"
foreach ($entry in $demoLogins) {
    Write-Host ("  {0,-16} {1}" -f $entry.Login, $entry.Role)
}
Write-Host ""
Write-Host ("The five seeded users share ASSETFLOW_DEMO_PASSWORD (the -Password value, or the environment " +
    "default). admin keeps the built-in Odoo password for a fresh database; change it before reusing " +
    "this database for anything else.")
Write-Host ""
Write-Host "Demo order: docs/instructions/demo-runbook.md (seven steps)."
Write-Host "Reset:      re-run ./scripts/demo.ps1."
Write-Host "Logs:       $logDir"
