param(
    [ValidateSet('local', 'external')]
    [string]$DatabaseMode,

    [string]$DatabaseUrl,

    [ValidateSet('development', 'single_server', 'split')]
    [string]$DeploymentProfile,

    [string]$RuntimeModules,
    [string]$StorageProvider,
    [string]$WorkerProfiles
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host ''
Write-Host 'Construction OS - Native Windows Setup'
Write-Host '--------------------------------------'
Write-Host 'Docker is not required for this setup.'
Write-Host ''

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Require-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget is required to install missing Windows dependencies. Install Microsoft App Installer, then run this script again.'
    }
}

function Get-DotEnvValue([string]$Key) {
    if (-not (Test-Path '.env')) {
        return $null
    }
    $line = Get-Content '.env' | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -Last 1
    if (-not $line) {
        return $null
    }
    return $line.Substring($Key.Length + 1).Trim()
}

function Set-DotEnvValue([string]$Key, [string]$Value) {
    $lines = if (Test-Path '.env') { @(Get-Content '.env') } else { @() }
    $pattern = "^$([regex]::Escape($Key))="
    $replacement = "$Key=$Value"
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match $pattern) {
            $found = $true
            $replacement
        }
        else {
            $line
        }
    }
    if (-not $found) {
        $updated += $replacement
    }
    Set-Content -Path '.env' -Value $updated -Encoding UTF8
}

function Get-Python312 {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $resolved = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                return $resolved.Trim()
            }
        }
        catch {}
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        try {
            $version = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '3.12') {
                return $python.Source
            }
        }
        catch {}
    }

    $known = Join-Path $env:LocalAppData 'Programs\Python\Python312\python.exe'
    if (Test-Path $known) {
        return $known
    }
    return $null
}

function Get-Psql {
    $psql = Get-Command psql -ErrorAction SilentlyContinue
    if ($psql) {
        return $psql.Source
    }

    $installRoot = Join-Path $env:ProgramFiles 'PostgreSQL'
    if (Test-Path $installRoot) {
        $candidate = Get-ChildItem $installRoot -Filter psql.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\bin\\psql\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }
    return $null
}

function Start-PostgresService {
    $service = Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'postgresql*' -or $_.DisplayName -like 'PostgreSQL*' } |
        Sort-Object Name -Descending |
        Select-Object -First 1

    if (-not $service) {
        throw 'PostgreSQL is installed but its Windows service was not found.'
    }
    if ($service.Status -ne 'Running') {
        Write-Host "Starting PostgreSQL service $($service.Name)..."
        try {
            Start-Service $service.Name
            $service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
        }
        catch {
            throw 'Could not start PostgreSQL. Open PowerShell as Administrator and run setup-local.ps1 again.'
        }
    }
}

function Test-LocalAppDatabase([string]$PsqlPath) {
    $previous = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = 'construction'
        & $PsqlPath -h localhost -U construction -d construction_os -tAc 'SELECT 1' *> $null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $env:PGPASSWORD = $previous
    }
}

function Initialize-LocalAppDatabase([string]$PsqlPath) {
    if (Test-LocalAppDatabase $PsqlPath) {
        Write-Host 'Construction OS local database already exists.'
        return
    }

    Write-Host ''
    Write-Host 'PostgreSQL needs one-time local database initialization.'
    Write-Host 'Enter the postgres administrator password selected during PostgreSQL installation.'
    $securePassword = Read-Host 'Postgres password' -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $previous = $env:PGPASSWORD
        $env:PGPASSWORD = $plainPassword

        $roleExists = (& $PsqlPath -h localhost -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='construction'" 2>$null).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not connect to PostgreSQL with the postgres administrator account.'
        }
        if ($roleExists -ne '1') {
            & $PsqlPath -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE construction LOGIN PASSWORD 'construction';"
            if ($LASTEXITCODE -ne 0) {
                throw 'Failed to create the local Construction OS database user.'
            }
        }

        $databaseExists = (& $PsqlPath -h localhost -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='construction_os'" 2>$null).Trim()
        if ($databaseExists -ne '1') {
            & $PsqlPath -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE construction_os OWNER construction;'
            if ($LASTEXITCODE -ne 0) {
                throw 'Failed to create the Construction OS database.'
            }
        }
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
        $env:PGPASSWORD = $previous
    }

    if (-not (Test-LocalAppDatabase $PsqlPath)) {
        throw 'Construction OS local database initialization did not complete successfully.'
    }
}

Refresh-Path

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env from .env.example.'
}

if (-not $DatabaseMode) {
    $DatabaseMode = Get-DotEnvValue 'DATABASE_MODE'
    if (-not $DatabaseMode) { $DatabaseMode = 'local' }
}
if (-not $DeploymentProfile) {
    $DeploymentProfile = Get-DotEnvValue 'DEPLOYMENT_PROFILE'
    if (-not $DeploymentProfile) { $DeploymentProfile = 'development' }
}
if (-not $RuntimeModules) {
    $RuntimeModules = Get-DotEnvValue 'RUNTIME_MODULES'
    if (-not $RuntimeModules) { $RuntimeModules = 'default' }
}
if (-not $StorageProvider) {
    $StorageProvider = Get-DotEnvValue 'STORAGE_PROVIDER'
    if (-not $StorageProvider) { $StorageProvider = 'local' }
}
if (-not $WorkerProfiles) {
    $WorkerProfiles = Get-DotEnvValue 'WORKER_PROFILES'
    if (-not $WorkerProfiles) { $WorkerProfiles = 'auto' }
}

$python = Get-Python312
if (-not $python) {
    Require-Winget
    Write-Host 'Python 3.12 is missing. Installing it...'
    winget install --exact --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 installation failed.' }
    Refresh-Path
    $python = Get-Python312
    if (-not $python) {
        throw 'Python 3.12 was installed but is not available yet. Open a new PowerShell window and run setup-local.ps1 again.'
    }
}

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Require-Winget
    Write-Host 'Node.js LTS is missing. Installing it...'
    winget install --exact --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Node.js installation failed.' }
    Refresh-Path
}
if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Node.js was installed but is not available yet. Open a new PowerShell window and run setup-local.ps1 again.'
}

if ($DatabaseMode -eq 'local') {
    $psql = Get-Psql
    if (-not $psql) {
        Require-Winget
        Write-Host 'PostgreSQL 17 is missing. Installing it for local database mode...'
        winget install --exact --id PostgreSQL.PostgreSQL.17 --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL installation failed.' }
        Refresh-Path
        $psql = Get-Psql
        if (-not $psql) {
            throw 'PostgreSQL was installed but psql was not found. Open a new PowerShell window and run setup-local.ps1 again.'
        }
    }
    Start-PostgresService
    Initialize-LocalAppDatabase $psql
    $DatabaseUrl = 'postgresql+asyncpg://construction:construction@localhost:5432/construction_os'
}
else {
    if (-not $DatabaseUrl) {
        $DatabaseUrl = Get-DotEnvValue 'DATABASE_URL'
        if (-not $DatabaseUrl -or $DatabaseUrl -match '@localhost[:/]') {
            $DatabaseUrl = Read-Host 'External PostgreSQL DATABASE_URL (postgresql+asyncpg://user:password@host:5432/database)'
        }
    }
    if (-not $DatabaseUrl) {
        throw 'External database mode requires DATABASE_URL.'
    }
    Write-Host 'External database mode selected. PostgreSQL will not be installed or started on this machine.'
}

Set-DotEnvValue 'DEPLOYMENT_PROFILE' $DeploymentProfile
Set-DotEnvValue 'DATABASE_MODE' $DatabaseMode
Set-DotEnvValue 'DATABASE_URL' $DatabaseUrl
Set-DotEnvValue 'STORAGE_PROVIDER' $StorageProvider
Set-DotEnvValue 'RUNTIME_MODULES' $RuntimeModules
Set-DotEnvValue 'WORKER_PROFILES' $WorkerProfiles

$venvPython = Join-Path $PSScriptRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating Python virtual environment...'
    & $python -m venv (Join-Path $PSScriptRoot 'apps\api\.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the Python virtual environment.' }
}

Write-Host 'Installing/updating API dependencies...'
Push-Location (Join-Path $PSScriptRoot 'apps\api')
try {
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Failed to update pip.' }
    & $venvPython -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install API dependencies.' }

    Write-Host 'Validating database connection and applying migrations...'
    & $venvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw 'Database connection or migration failed. Check DATABASE_URL and database permissions.'
    }
}
finally {
    Pop-Location
}

Write-Host 'Installing/updating Web dependencies...'
Push-Location (Join-Path $PSScriptRoot 'apps\web')
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install Web dependencies.' }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host "Deployment profile: $DeploymentProfile"
Write-Host "Database mode:      $DatabaseMode"
Write-Host "Storage provider:   $StorageProvider"
Write-Host "Runtime modules:    $RuntimeModules"
Write-Host "Worker profiles:    $WorkerProfiles"
Write-Host ''
Write-Host 'Start Construction OS with:'
Write-Host '    .\start-local.ps1' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Web: http://localhost:3000'
