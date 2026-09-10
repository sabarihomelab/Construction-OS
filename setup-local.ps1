$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host ''
Write-Host 'Construction OS - Local Setup'
Write-Host '-----------------------------'

function Refresh-DockerPath {
    $dockerPath = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
    if (Test-Path $dockerPath) {
        $env:Path = "$dockerPath;$env:Path"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Refresh-DockerPath
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker Desktop is not installed. Installing it with winget...'

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Docker Desktop is required. winget is not available, so install Docker Desktop manually and run this script again.'
    }

    winget install --exact --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Desktop installation failed.'
    }

    Refresh-DockerPath

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host ''
        Write-Host 'Docker Desktop was installed.'
        Write-Host 'Open Docker Desktop once, finish its first-run setup, then run setup-local.ps1 again.'
        exit 0
    }
}

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env from .env.example.'
}
else {
    Write-Host '.env already exists. Keeping your existing values.'
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path $dockerDesktop) {
        Write-Host 'Docker Desktop is installed but not running.'
        Write-Host 'Starting Docker Desktop...'
        Start-Process $dockerDesktop
        Write-Host 'When Docker Desktop shows Ready, run setup-local.ps1 again.'
        exit 0
    }
    throw 'Docker is installed but the Docker engine is not running.'
}

Write-Host 'Preparing PostgreSQL image...'
docker compose pull postgres
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to download the PostgreSQL image.'
}

Write-Host 'Building API and Web images and installing application dependencies...'
docker compose build api web
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to build the local application images.'
}

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host ''
Write-Host 'Start Construction OS with:'
Write-Host ''
Write-Host '    docker compose up' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Then open:'
Write-Host '    http://localhost:3000'
Write-Host ''
Write-Host 'API:'
Write-Host '    http://localhost:8000'
Write-Host 'API docs:'
Write-Host '    http://localhost:8000/docs'
Write-Host ''
Write-Host 'To stop it later, press Ctrl+C, then run:'
Write-Host '    docker compose down'
