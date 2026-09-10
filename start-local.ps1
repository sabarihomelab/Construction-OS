$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host ''
Write-Host 'Construction OS - Start Local'
Write-Host '-----------------------------'

$venvPython = Join-Path $PSScriptRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    throw 'Local setup is not complete. Run .\setup-local.ps1 first.'
}

if (-not (Test-Path (Join-Path $PSScriptRoot 'apps\web\node_modules'))) {
    throw 'Web dependencies are not installed. Run .\setup-local.ps1 first.'
}

if (-not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    throw '.env is missing. Run .\setup-local.ps1 first.'
}

$postgresService = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'postgresql*' -or $_.DisplayName -like 'PostgreSQL*' } |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $postgresService) {
    throw 'PostgreSQL service was not found. Run .\setup-local.ps1 first.'
}

if ($postgresService.Status -ne 'Running') {
    Write-Host "Starting PostgreSQL service $($postgresService.Name)..."
    try {
        Start-Service $postgresService.Name
        $postgresService.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    }
    catch {
        throw 'Could not start PostgreSQL. Open PowerShell as Administrator and run .\start-local.ps1 again.'
    }
}

Write-Host 'Applying any new database migrations...'
Push-Location (Join-Path $PSScriptRoot 'apps\api')
try {
    & $venvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw 'Database migration failed. Run .\setup-local.ps1 again and review the error.'
    }
}
finally {
    Pop-Location
}

$apiCommand = "Set-Location '$($PSScriptRoot.Replace("'", "''"))\apps\api'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
$webCommand = "Set-Location '$($PSScriptRoot.Replace("'", "''"))\apps\web'; npm run dev"

Write-Host 'Starting API...'
Start-Process powershell.exe -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $apiCommand
)

Write-Host 'Starting Web app...'
Start-Process powershell.exe -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $webCommand
)

Write-Host 'Waiting for local services...'
$apiReady = $false
$webReady = $false

for ($attempt = 1; $attempt -le 60; $attempt++) {
    if (-not $apiReady) {
        try {
            $response = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2
            $apiReady = ($response.StatusCode -eq 200)
        }
        catch {}
    }

    if (-not $webReady) {
        try {
            $response = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 2
            $webReady = ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
        }
        catch {}
    }

    if ($apiReady -and $webReady) {
        break
    }

    Start-Sleep -Seconds 1
}

Write-Host ''
if ($apiReady -and $webReady) {
    Write-Host 'Construction OS is running.' -ForegroundColor Green
    Write-Host 'Web:      http://localhost:3000'
    Write-Host 'API:      http://localhost:8000'
    Write-Host 'API Docs: http://localhost:8000/docs'
    Write-Host ''
    Write-Host 'The API and Web app are running in the two PowerShell windows that were opened.'
    Start-Process 'http://localhost:3000'
}
else {
    Write-Host 'One or more services did not become ready.' -ForegroundColor Yellow
    Write-Host 'Check the API and Web PowerShell windows for the startup error.'
}
