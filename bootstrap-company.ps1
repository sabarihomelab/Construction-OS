param(
    [Parameter(Mandatory = $true)]
    [string]$CompanyName,

    [Parameter(Mandatory = $true)]
    [string]$CompanySlug,

    [string]$LegalName,

    [Parameter(Mandatory = $true)]
    [string]$AdminEmail,

    [Parameter(Mandatory = $true)]
    [string]$AdminDisplayName
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Construction OS API environment is not installed. Run .\setup.ps1 first.'
}

$args = @(
    '-m',
    'app.runtime.bootstrap_company',
    '--company-name', $CompanyName,
    '--company-slug', $CompanySlug,
    '--admin-email', $AdminEmail,
    '--admin-display-name', $AdminDisplayName
)
if ($LegalName) {
    $args += @('--legal-name', $LegalName)
}

Push-Location (Join-Path $PSScriptRoot 'apps\api')
try {
    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw 'Company bootstrap failed.'
    }
}
finally {
    Pop-Location
}
