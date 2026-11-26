param(
    [switch]$SkipStart
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$server = Join-Path $root "server"
$python = Join-Path $server ".venv\Scripts\python.exe"

$mysqlService = Get-Service -Name "MySQL84" -ErrorAction SilentlyContinue
if (-not $mysqlService) {
    throw "MySQL84 service was not found. Install/configure MySQL Server 8.4 first."
}
if ($mysqlService.Status -ne "Running") {
    throw "MySQL84 is not running. Start the service, then run setup.ps1 again."
}

if (-not (Test-Path $python)) {
    py -m venv (Join-Path $server ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python virtual environment." }
}

& $python -m pip install -r (Join-Path $server "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install backend requirements." }

& $python (Join-Path $server "scripts\prepare_environment.py")
if ($LASTEXITCODE -ne 0) { throw "Could not prepare server/.env." }

Write-Host "Database setup will securely prompt for MySQL administrator and application passwords."
& $python (Join-Path $server "scripts\setup_database.py")
if ($LASTEXITCODE -ne 0) { throw "MySQL initialization failed; no server was started." }

Write-Host "Create demonstration accounts for roles that do not already have an account."
& $python (Join-Path $server "scripts\create_demo_accounts.py")
if ($LASTEXITCODE -ne 0) { throw "Demonstration account setup failed; no server was started." }

Write-Host "Create the first administrator only if one is still missing."
& $python (Join-Path $server "scripts\create_admin.py")
if ($LASTEXITCODE -ne 0) { throw "Administrator setup failed; no server was started." }

if ($SkipStart) {
    Write-Host "Database and account setup are complete. Start the app using the README commands."
    exit 0
}

$pythonCommand = "`$host.UI.RawUI.WindowTitle = 'AgriLearn Flask API'; Set-Location -LiteralPath '$server'; & '.venv\Scripts\python.exe' run.py"
$frontendCommand = "`$host.UI.RawUI.WindowTitle = 'AgriLearn Frontend'; Set-Location -LiteralPath '$root'; python -m http.server 8000 --bind 127.0.0.1"
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $pythonCommand)
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $frontendCommand)

$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health/database" -TimeoutSec 2
        if ($health.data.database -eq "connected") {
            $ready = $true
            break
        }
    } catch {
        continue
    }
}
if (-not $ready) {
    throw "Flask did not report a healthy MySQL connection. Inspect the AgriLearn Flask window."
}

Write-Host "AgriLearn is running at http://127.0.0.1:8000 (API: http://127.0.0.1:5000)."
Start-Process "http://127.0.0.1:8000"
