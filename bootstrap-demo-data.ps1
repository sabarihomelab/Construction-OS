param(
    [Parameter(Mandatory = $true)]
    [string]$AdminEmail,

    [string]$ProjectNumber = 'DEMO-001',
    [string]$ProjectName = 'Riverside Residency - Phase 1'
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Construction OS API environment is not installed. Run .\setup.ps1 first.'
}
if (-not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    throw 'Construction OS environment is not configured. Run .\setup.ps1 first.'
}

$args = @(
    '-m',
    'app.runtime.bootstrap_demo_data',
    '--admin-email', $AdminEmail,
    '--project-number', $ProjectNumber,
    '--project-name', $ProjectName
)

Push-Location (Join-Path $PSScriptRoot 'apps\api')
try {
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw 'Demo data bootstrap failed. Review the error above.'
    }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Demo data is ready for Android self-testing.' -ForegroundColor Green
Write-Host "Project: $ProjectNumber - $ProjectName"
Write-Host 'Run the command again safely if needed; an existing demo project is left unchanged.'
