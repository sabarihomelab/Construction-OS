$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host ''
Write-Host 'Construction OS - Native Windows Setup'
Write-Host '--------------------------------------'
Write-Host 'This setup does not use Docker.'
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

function Test-AppDatabase([string]$PsqlPath) {
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

function Initialize-AppDatabase([string]$PsqlPath) {
    if (Test-AppDatabase $PsqlPath) {
        Write-Host 'Construction OS database already exists.'
        return
    }

    Write-Host ''
    Write-Host 'PostgreSQL needs one-time database initialization.'
    Write-Host 'Enter the postgres administrator password you chose during PostgreSQL installation.'
    $securePassword = Read-Host 'Postgres password' -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $previous = $env:PGPASSWORD
        $env:PGPASSWORD = $plainPassword

        $roleExists = (& $PsqlPath -h localhost -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='construction'" 2>$null).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not connect to PostgreSQL with the postgres administrator account. Check the password and run setup-local.ps1 again.'
        }

        if ($roleExists -ne '1') {
            & $PsqlPath -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE construction LOGIN PASSWORD 'construction';"
            if ($LASTEXITCODE -ne 0) {
                throw 'Failed to create the local Construction OS database user.'
            }
        }

        $databaseExists = (& $PsqlPath -h localhost -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='construction_os'" 2>$null).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to check the Construction OS database.'
        }

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

    if (-not (Test-AppDatabase $PsqlPath)) {
        throw 'Construction OS database initialization did not complete successfully.'
    }

    Write-Host 'Construction OS database is ready.'
}

Refresh-Path

$python = Get-Python312
if (-not $python) {
    Require-Winget
    Write-Host 'Python 3.12 is missing. Installing it...'
    winget install --exact --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'Python 3.12 installation failed.'
    }
    Refresh-Path
    $python = Get-Python312
    if (-not $python) {
        throw 'Python 3.12 was installed but is not available yet. Open a new PowerShell window and run setup-local.ps1 again.'
    }
}
Write-Host "Python: $python"

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Require-Winget
    Write-Host 'Node.js LTS is missing. Installing it...'
    winget install --exact --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'Node.js installation failed.'
    }
    Refresh-Path
}

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Node.js was installed but is not available yet. Open a new PowerShell window and run setup-local.ps1 again.'
}
Write-Host "Node: $(node --version)"
Write-Host "npm:  $(npm --version)"

$psql = Get-Psql
if (-not $psql) {
    Require-Winget
    Write-Host 'PostgreSQL 17 is missing. Installing it...'
    Write-Host 'The PostgreSQL installer may ask you to choose an administrator password. Remember that password for this setup.'
    winget install --exact --id PostgreSQL.PostgreSQL.17 --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'PostgreSQL installation failed.'
    }
    Refresh-Path
    $psql = Get-Psql
    if (-not $psql) {
        throw 'PostgreSQL was installed but psql was not found. Open a new PowerShell window and run setup-local.ps1 again.'
    }
}
Write-Host "PostgreSQL client: $psql"

Start-PostgresService
Initialize-AppDatabase $psql

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created local .env from .env.example.'
}
else {
    Write-Host '.env already exists. Keeping your existing values.'
}

$venvPython = Join-Path $PSScriptRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating Python virtual environment...'
    & $python -m venv (Join-Path $PSScriptRoot 'apps\api\.venv')
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create the Python virtual environment.'
    }
}

Write-Host 'Installing/updating API dependencies...'
Push-Location (Join-Path $PSScriptRoot 'apps\api')
try {
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to update pip.'
    }
    & $venvPython -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to install API dependencies.'
    }

    Write-Host 'Applying database migrations...'
    & $venvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw 'Database migration failed.'
    }
}
finally {
    Pop-Location
}

Write-Host 'Installing/updating Web dependencies...'
Push-Location (Join-Path $PSScriptRoot 'apps\web')
try {
    npm install
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to install Web dependencies.'
    }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host ''
Write-Host 'From now on, start Construction OS with:'
Write-Host ''
Write-Host '    .\start-local.ps1' -ForegroundColor Cyan
Write-Host ''
Write-Host 'The launcher will start the API and Web app and open:'
Write-Host '    http://localhost:3000'
