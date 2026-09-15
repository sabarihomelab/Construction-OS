param(
    [ValidateSet('auto', 'install', 'add-modules', 'upgrade', 'reconfigure', 'repair', 'validate')]
    [string]$Mode = 'auto',
    [string]$InstallationPath,
    [string]$EnvironmentName,
    [ValidateSet('development', 'test', 'staging', 'production')]
    [string]$Environment,
    [ValidateSet('local', 'external')]
    [string]$DatabaseMode,
    [string]$DatabaseUrl,
    [ValidateSet('development', 'single_server', 'split')]
    [string]$DeploymentProfile,
    [string]$RuntimeModules,
    [string]$WebOrigin,
    [string]$ApiPublicUrl,
    [string]$ExternalBackupReference,
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'
$SourceRoot = $PSScriptRoot
$InstallRoot = if ($InstallationPath) { [IO.Path]::GetFullPath($InstallationPath) } else { $SourceRoot }

if ($InstallRoot -ne $SourceRoot) {
    throw 'This release currently supports setup from the installed application folder. Versioned release-package copy/swap will be added before production packaging. Run setup.ps1 from the existing Construction OS installation path.'
}

Set-Location $InstallRoot
$StateDir = Join-Path $InstallRoot '.construction-os'
$StatePath = Join-Path $StateDir 'install-state.json'
$BackupDir = Join-Path $StateDir 'backups\database'
$RollbackDir = Join-Path $StateDir 'rollback'
$EnvPath = Join-Path $InstallRoot '.env'

function Read-Value([string]$Prompt, [string]$DefaultValue) {
    if ($NonInteractive) { return $DefaultValue }
    $suffix = if ($DefaultValue) { " [$DefaultValue]" } else { '' }
    $value = Read-Host "$Prompt$suffix"
    if ([string]::IsNullOrWhiteSpace($value)) { return $DefaultValue }
    return $value.Trim()
}

function Read-Choice([string]$Prompt, [string[]]$Choices, [int]$DefaultIndex = 0) {
    if ($NonInteractive) { return $DefaultIndex }
    Write-Host ''
    for ($i = 0; $i -lt $Choices.Count; $i++) {
        Write-Host "  $($i + 1). $($Choices[$i])"
    }
    while ($true) {
        $raw = Read-Host "$Prompt [$($DefaultIndex + 1)]"
        if ([string]::IsNullOrWhiteSpace($raw)) { return $DefaultIndex }
        $number = 0
        if ([int]::TryParse($raw, [ref]$number) -and $number -ge 1 -and $number -le $Choices.Count) {
            return $number - 1
        }
        Write-Host 'Enter one of the displayed numbers.' -ForegroundColor Yellow
    }
}

function Get-EnvValue([string]$Key) {
    if (-not (Test-Path $EnvPath)) { return $null }
    $line = Get-Content $EnvPath | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -Last 1
    if (-not $line) { return $null }
    return $line.Substring($Key.Length + 1).Trim()
}

function Set-EnvValue([string]$Key, [string]$Value) {
    $lines = if (Test-Path $EnvPath) { @(Get-Content $EnvPath) } else { @() }
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
    if (-not $found) { $updated += $replacement }
    Set-Content -Path $EnvPath -Value $updated -Encoding UTF8
}

function Get-State {
    if (-not (Test-Path $StatePath)) { return $null }
    return Get-Content $StatePath -Raw | ConvertFrom-Json
}

function Get-ReleaseVersion {
    $path = Join-Path $InstallRoot 'VERSION'
    if (Test-Path $path) { return (Get-Content $path -Raw).Trim() }
    return 'development'
}

function Get-Python312 {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $resolved = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) { return $resolved.Trim() }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $version = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '3.12') { return $python.Source }
    }
    return $null
}

function Ensure-Python312 {
    $python = Get-Python312
    if ($python) { return $python }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Python 3.12 is required and winget is unavailable.'
    }
    Write-Host 'Installing Python 3.12...'
    winget install --exact --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 installation failed.' }
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
    $python = Get-Python312
    if (-not $python) { throw 'Python 3.12 was installed but is not available in this PowerShell session yet.' }
    return $python
}

function Get-ModuleCatalog([string]$PythonPath) {
    $previous = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $InstallRoot 'apps\api'
        $json = & $PythonPath -m app.runtime.installer_cli catalog
        if ($LASTEXITCODE -ne 0) { throw 'Could not load the release module manifest.' }
        return @($json | ConvertFrom-Json)
    }
    finally {
        $env:PYTHONPATH = $previous
    }
}

function Resolve-Modules([string]$PythonPath, [string]$RawModules) {
    $previous = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $InstallRoot 'apps\api'
        $json = & $PythonPath -m app.runtime.installer_cli resolve $RawModules
        if ($LASTEXITCODE -ne 0) { throw 'Could not resolve module dependencies.' }
        return @($json | ConvertFrom-Json)
    }
    finally {
        $env:PYTHONPATH = $previous
    }
}

function Select-InitialModules([object[]]$Catalog) {
    Write-Host ''
    Write-Host 'Business modules available in this release:' -ForegroundColor Cyan
    for ($i = 0; $i -lt $Catalog.Count; $i++) {
        $heavy = if ($Catalog[$i].heavy_runtime) { ' [heavy runtime]' } else { '' }
        Write-Host "  $($i + 1). $($Catalog[$i].name) ($($Catalog[$i].key))$heavy"
    }
    if ($NonInteractive) { return 'projects' }
    Write-Host 'Enter comma-separated module numbers. Required dependencies are added automatically.'
    while ($true) {
        $raw = Read-Host 'Modules [1]'
        if ([string]::IsNullOrWhiteSpace($raw)) { return [string]$Catalog[0].key }
        $keys = @()
        $valid = $true
        foreach ($token in ($raw -split ',')) {
            $number = 0
            if (-not [int]::TryParse($token.Trim(), [ref]$number) -or $number -lt 1 -or $number -gt $Catalog.Count) {
                $valid = $false
                break
            }
            $keys += [string]$Catalog[$number - 1].key
        }
        if ($valid -and $keys.Count -gt 0) { return (($keys | Select-Object -Unique) -join ',') }
        Write-Host 'Choose valid module numbers.' -ForegroundColor Yellow
    }
}

function Select-AdditionalModules([object[]]$Catalog, [string[]]$Installed) {
    $uninstalled = @($Catalog | Where-Object { $Installed -notcontains [string]$_.key })
    Write-Host ''
    Write-Host "Installed modules: $($Installed -join ', ')"
    if ($uninstalled.Count -eq 0) {
        Write-Host 'No uninstalled modules are available in this release.' -ForegroundColor Green
        return $null
    }
    Write-Host 'Uninstalled modules:' -ForegroundColor Cyan
    for ($i = 0; $i -lt $uninstalled.Count; $i++) {
        Write-Host "  $($i + 1). $($uninstalled[$i].name) ($($uninstalled[$i].key))"
    }
    if ($NonInteractive) { throw 'Specify -RuntimeModules when using add-modules non-interactively.' }
    while ($true) {
        $raw = Read-Host 'Modules to add (comma-separated numbers, blank to cancel)'
        if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
        $keys = @($Installed)
        $valid = $true
        foreach ($token in ($raw -split ',')) {
            $number = 0
            if (-not [int]::TryParse($token.Trim(), [ref]$number) -or $number -lt 1 -or $number -gt $uninstalled.Count) {
                $valid = $false
                break
            }
            $keys += [string]$uninstalled[$number - 1].key
        }
        if ($valid) { return (($keys | Select-Object -Unique) -join ',') }
        Write-Host 'Choose valid module numbers.' -ForegroundColor Yellow
    }
}

function Find-PostgresTool([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $root = Join-Path $env:ProgramFiles 'PostgreSQL'
    if (-not (Test-Path $root)) { return $null }
    $candidate = Get-ChildItem $root -Filter "$Name.exe" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\bin\\' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($candidate) { return $candidate.FullName }
    return $null
}

function Backup-Database([string]$Url, [string]$DbMode) {
    $pgDump = Find-PostgresTool 'pg_dump'
    if (-not $pgDump) {
        if ($DbMode -eq 'external' -and $ExternalBackupReference) {
            Write-Host "Using external backup reference: $ExternalBackupReference" -ForegroundColor Yellow
            return "external:$ExternalBackupReference"
        }
        throw 'A verified database backup is required before migration. pg_dump was not found. Install compatible PostgreSQL client tools or provide -ExternalBackupReference for a verified managed-database snapshot.'
    }

    $normalized = $Url -replace '^postgresql\+asyncpg://', 'postgresql://'
    $uri = [Uri]$normalized
    $userInfo = [Uri]::UnescapeDataString($uri.UserInfo).Split(':', 2)
    if ($userInfo.Count -lt 1 -or -not $userInfo[0]) { throw 'DATABASE_URL does not contain a PostgreSQL username.' }
    $dbUser = $userInfo[0]
    $dbPassword = if ($userInfo.Count -gt 1) { $userInfo[1] } else { '' }
    $dbName = $uri.AbsolutePath.TrimStart('/')
    $dbPort = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }

    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    $path = Join-Path $BackupDir ("construction-os-{0}.dump" -f [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
    Write-Host "Creating pre-migration backup: $path"
    $previousPassword = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $dbPassword
        & $pgDump --format=custom --no-owner --no-privileges --host=$($uri.Host) --port=$dbPort --username=$dbUser --file=$path $dbName
        if ($LASTEXITCODE -ne 0) { throw 'Database backup failed. Migration has not started.' }
    }
    finally {
        $env:PGPASSWORD = $previousPassword
    }
    $file = Get-Item $path -ErrorAction Stop
    if ($file.Length -le 0) { throw 'Database backup is empty. Migration has not started.' }
    $pgRestore = Find-PostgresTool 'pg_restore'
    if ($pgRestore) {
        & $pgRestore --list $path *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Database backup verification failed. Migration has not started.' }
    }
    Write-Host 'Database backup created and verified.' -ForegroundColor Green
    return $path
}

function Backup-Environment {
    if (-not (Test-Path $EnvPath)) { return $null }
    New-Item -ItemType Directory -Path $RollbackDir -Force | Out-Null
    $path = Join-Path $RollbackDir ("env-{0}.bak" -f [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
    Copy-Item $EnvPath $path -Force
    return $path
}

function Test-Url([string]$Value, [string]$Label) {
    $uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri)) { throw "$Label is not a valid URL." }
    if (@('http', 'https') -notcontains $uri.Scheme) { throw "$Label must use HTTP or HTTPS." }
    return $uri
}

function Test-DatabaseNetwork([string]$Url) {
    $normalized = $Url -replace '^postgresql\+asyncpg://', 'postgresql://'
    $uri = [Uri]$normalized
    $port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
    Write-Host "Testing database server $($uri.Host):$port..."
    $result = Test-NetConnection -ComputerName $uri.Host -Port $port -WarningAction SilentlyContinue
    if (-not $result.TcpTestSucceeded) { throw "Database server $($uri.Host):$port is not reachable." }
    Write-Host 'Database server network test passed.' -ForegroundColor Green
}

function Get-DatabaseSummary([string]$Url) {
    try {
        $normalized = $Url -replace '^postgresql\+asyncpg://', 'postgresql://'
        $uri = [Uri]$normalized
        $port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
        return "$($uri.Host):$port/$($uri.AbsolutePath.TrimStart('/'))"
    }
    catch { return 'configured' }
}

function Test-TemporaryApi([string[]]$ExpectedModules) {
    $python = Join-Path $InstallRoot 'apps\api\.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { throw 'API virtual environment is missing after setup.' }

    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()

    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    $stdout = Join-Path $StateDir 'readiness.stdout.log'
    $stderr = Join-Path $StateDir 'readiness.stderr.log'
    Remove-Item $stdout, $stderr -Force -ErrorAction SilentlyContinue

    Write-Host "Testing a temporary API instance on 127.0.0.1:$port..."
    $process = Start-Process -FilePath $python -WorkingDirectory (Join-Path $InstallRoot 'apps\api') -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', [string]$port
    ) -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    try {
        $response = $null
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if ($process.HasExited) { break }
            try {
                $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health/ready" -TimeoutSec 2
                if ($response.status -eq 'ready') { break }
            }
            catch {}
            Start-Sleep -Seconds 1
        }
        if (-not $response -or $response.status -ne 'ready') {
            $details = if (Test-Path $stderr) { Get-Content $stderr -Raw } else { '' }
            throw "API readiness test failed. $details"
        }
        $reported = @($response.runtime_modules | ForEach-Object { [string]$_ })
        $missing = @($ExpectedModules | Where-Object { $reported -notcontains $_ })
        if ($missing.Count -gt 0) { throw "API did not activate expected modules: $($missing -join ', ')" }
        Write-Host 'API readiness response and module composition are valid.' -ForegroundColor Green
    }
    finally {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
}

function Get-MigrationVersion {
    $python = Join-Path $InstallRoot 'apps\api\.venv\Scripts\python.exe'
    Push-Location (Join-Path $InstallRoot 'apps\api')
    try {
        $current = & $python -m alembic current 2>$null
        if ($LASTEXITCODE -ne 0) { return 'unknown' }
        return (($current | Out-String).Trim())
    }
    finally { Pop-Location }
}

function Write-State([object]$PreviousState, [string[]]$Modules, [string]$BackupReference, [string]$CompletedMode) {
    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    $now = [DateTime]::UtcNow.ToString('o')
    $installationId = if ($PreviousState -and $PreviousState.installation_id) { [string]$PreviousState.installation_id } else { [guid]::NewGuid().ToString() }
    $installedAt = if ($PreviousState -and $PreviousState.installed_at_utc) { [string]$PreviousState.installed_at_utc } else { $now }
    $history = @()
    if ($PreviousState -and $PreviousState.history) { $history = @($PreviousState.history) }
    $history += [ordered]@{
        completed_at_utc = $now
        action = $CompletedMode
        release_version = Get-ReleaseVersion
        modules = @($Modules)
        backup = $BackupReference
        migration = Get-MigrationVersion
    }
    if ($history.Count -gt 50) { $history = @($history | Select-Object -Last 50) }

    $record = [ordered]@{
        schema_version = 1
        installation_id = $installationId
        installation_path = $InstallRoot
        installed_at_utc = $installedAt
        updated_at_utc = $now
        release_version = Get-ReleaseVersion
        environment = $Environment
        environment_name = $EnvironmentName
        deployment_profile = $DeploymentProfile
        database_mode = $DatabaseMode
        database_endpoint = Get-DatabaseSummary $DatabaseUrl
        storage_provider = 'local'
        runtime_modules = @($Modules)
        worker_profiles = 'auto'
        web_origin = $WebOrigin
        api_public_url = $ApiPublicUrl
        last_backup = $BackupReference
        last_migration = Get-MigrationVersion
        history = $history
    }
    $record | ConvertTo-Json -Depth 8 | Set-Content -Path $StatePath -Encoding UTF8

    try {
        $machineDir = Join-Path $env:ProgramData 'ConstructionOS'
        New-Item -ItemType Directory -Path $machineDir -Force | Out-Null
        @{
            schema_version = 1
            installation_id = $installationId
            installation_path = $InstallRoot
            updated_at_utc = $now
        } | ConvertTo-Json | Set-Content -Path (Join-Path $machineDir 'installation.json') -Encoding UTF8
    }
    catch {
        Write-Host 'Could not write machine-wide installation pointer; local installer state is still valid.' -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host 'Construction OS - Setup and Maintenance' -ForegroundColor Cyan
Write-Host '---------------------------------------'
Write-Host "Installation path: $InstallRoot"
Write-Host "Release:           $(Get-ReleaseVersion)"

$systemPython = Ensure-Python312
$catalog = Get-ModuleCatalog $systemPython
$state = Get-State
$existing = (Test-Path $EnvPath) -or ($null -ne $state)

if ($Mode -eq 'auto') {
    if (-not $existing) {
        $Mode = 'install'
    }
    elseif ($NonInteractive) {
        $Mode = 'validate'
    }
    else {
        if ($state) { Write-Host "Existing installation: $($state.environment_name) / $($state.release_version)" -ForegroundColor Green }
        $index = Read-Choice 'Choose action' @(
            'Add business modules',
            'Upgrade/refresh this version',
            'Reconfigure environment settings',
            'Repair dependencies and validate',
            'Validate only',
            'Exit'
        ) 0
        $Mode = @('add-modules', 'upgrade', 'reconfigure', 'repair', 'validate', 'exit')[$index]
        if ($Mode -eq 'exit') { Write-Host 'No changes made.'; exit 0 }
    }
}

$currentEnvironment = Get-EnvValue 'ENVIRONMENT'
$currentEnvironmentName = Get-EnvValue 'ENVIRONMENT_NAME'
$currentDatabaseMode = Get-EnvValue 'DATABASE_MODE'
$currentDatabaseUrl = Get-EnvValue 'DATABASE_URL'
$currentProfile = Get-EnvValue 'DEPLOYMENT_PROFILE'
$currentModulesRaw = Get-EnvValue 'RUNTIME_MODULES'
$currentWebOrigin = Get-EnvValue 'WEB_ORIGIN'
$currentApiUrl = Get-EnvValue 'NEXT_PUBLIC_API_URL'
if (-not $currentModulesRaw) { $currentModulesRaw = 'projects' }
$currentModules = @(Resolve-Modules $systemPython $currentModulesRaw)

if ($Mode -eq 'validate') {
    if (-not $existing) { throw 'No existing installation was found.' }
    $DatabaseMode = if ($currentDatabaseMode) { $currentDatabaseMode } else { 'local' }
    $DatabaseUrl = $currentDatabaseUrl
    if ($DatabaseMode -eq 'external') { Test-DatabaseNetwork $DatabaseUrl }
    Test-TemporaryApi $currentModules
    Write-Host 'Installation validation passed.' -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $EnvPath)) { Copy-Item (Join-Path $InstallRoot '.env.example') $EnvPath }

if (-not $Environment) { $Environment = Read-Value 'Environment type (development/test/staging/production)' $(if ($currentEnvironment) { $currentEnvironment } else { 'development' }) }
if (-not $EnvironmentName) { $EnvironmentName = Read-Value 'Environment name' $(if ($currentEnvironmentName) { $currentEnvironmentName } else { 'Local Development' }) }
if (-not $DeploymentProfile) { $DeploymentProfile = Read-Value 'Deployment profile (development/single_server/split)' $(if ($currentProfile) { $currentProfile } else { 'development' }) }
if (-not $DatabaseMode) { $DatabaseMode = Read-Value 'Database mode (local/external)' $(if ($currentDatabaseMode) { $currentDatabaseMode } else { 'local' }) }

if ($DatabaseMode -eq 'external') {
    if (-not $DatabaseUrl) { $DatabaseUrl = Read-Value 'External PostgreSQL DATABASE_URL' $(if ($currentDatabaseMode -eq 'external') { $currentDatabaseUrl } else { '' }) }
    if (-not $DatabaseUrl) { throw 'External database mode requires DATABASE_URL.' }
    Test-DatabaseNetwork $DatabaseUrl
}
else {
    $DatabaseUrl = 'postgresql+asyncpg://construction:construction@localhost:5432/construction_os'
}

if ($existing -and $currentDatabaseUrl -and $DatabaseUrl -ne $currentDatabaseUrl) {
    throw 'Changing the database endpoint of an existing installation requires an explicit data-move/export-restore workflow. Normal setup will not silently point existing data at another database.'
}

if (-not $WebOrigin) { $WebOrigin = Read-Value 'Web origin' $(if ($currentWebOrigin) { $currentWebOrigin } else { 'http://localhost:3000' }) }
if (-not $ApiPublicUrl) { $ApiPublicUrl = Read-Value 'API public URL' $(if ($currentApiUrl) { $currentApiUrl } else { 'http://localhost:8000/api/v1' }) }
$webUri = Test-Url $WebOrigin 'WEB_ORIGIN'
[void](Test-Url $ApiPublicUrl 'NEXT_PUBLIC_API_URL')
if ($Environment -eq 'production' -and $webUri.Scheme -ne 'https') { throw 'Production WEB_ORIGIN must use HTTPS.' }

if ($RuntimeModules) {
    $resolvedModules = @(Resolve-Modules $systemPython $RuntimeModules)
}
elseif ($Mode -eq 'install') {
    $selected = Select-InitialModules $catalog
    $resolvedModules = @(Resolve-Modules $systemPython $selected)
}
elseif ($Mode -eq 'add-modules') {
    $selected = Select-AdditionalModules $catalog $currentModules
    if (-not $selected) { Write-Host 'No module changes made.'; exit 0 }
    $resolvedModules = @(Resolve-Modules $systemPython $selected)
}
else {
    $resolvedModules = $currentModules
}

if ($resolvedModules.Count -eq 0) { throw 'At least one business module must be selected.' }
$RuntimeModules = (($resolvedModules | Select-Object -Unique) -join ',')

Write-Host ''
Write-Host 'Configuration to apply' -ForegroundColor Cyan
Write-Host "  Environment:        $EnvironmentName ($Environment)"
Write-Host "  Deployment profile: $DeploymentProfile"
Write-Host "  Database:           $DatabaseMode / $(Get-DatabaseSummary $DatabaseUrl)"
Write-Host "  Modules:            $RuntimeModules"
Write-Host "  Web origin:         $WebOrigin"
Write-Host "  API URL:            $ApiPublicUrl"
if (-not $NonInteractive) {
    $confirmation = Read-Choice 'Continue?' @('Continue', 'Cancel') 0
    if ($confirmation -ne 0) { Write-Host 'No changes made.'; exit 0 }
}

$backupReference = $null
$envRollback = $null
if ($existing) {
    if (-not $currentDatabaseUrl) { throw 'Existing installation has no DATABASE_URL. Migration is blocked until database configuration is repaired.' }
    $backupReference = Backup-Database $currentDatabaseUrl $currentDatabaseMode
    $envRollback = Backup-Environment
}

Set-EnvValue 'ENVIRONMENT' $Environment
Set-EnvValue 'ENVIRONMENT_NAME' $EnvironmentName
Set-EnvValue 'WEB_ORIGIN' $WebOrigin
Set-EnvValue 'NEXT_PUBLIC_API_URL' $ApiPublicUrl
if ($Environment -eq 'production') { Set-EnvValue 'SESSION_COOKIE_SECURE' 'true' }

try {
    & (Join-Path $InstallRoot 'setup-local.ps1') -DatabaseMode $DatabaseMode -DatabaseUrl $DatabaseUrl -DeploymentProfile $DeploymentProfile -RuntimeModules $RuntimeModules -StorageProvider 'local' -WorkerProfiles 'auto'
    if ($LASTEXITCODE -ne 0) { throw 'Low-level dependency/database setup failed.' }
    Test-TemporaryApi $resolvedModules
}
catch {
    if ($envRollback -and (Test-Path $envRollback)) {
        Copy-Item $envRollback $EnvPath -Force
        Write-Host 'Previous environment configuration restored.' -ForegroundColor Yellow
    }
    throw
}

Write-State $state $resolvedModules $backupReference $Mode
Write-Host ''
Write-Host 'Setup completed successfully.' -ForegroundColor Green
Write-Host "State:   $StatePath"
if ($backupReference) { Write-Host "Backup:  $backupReference" }
Write-Host "Modules: $($resolvedModules -join ', ')"
Write-Host ''
Write-Host 'Run .\setup.ps1 again later to add newly available modules, upgrade, reconfigure, repair or validate this installation.'
