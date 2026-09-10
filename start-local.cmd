@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title Construction OS Local Development

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=start"

if /I "%ACTION%"=="help" goto :help
if /I "%ACTION%"=="stop" goto :require_docker
if /I "%ACTION%"=="logs" goto :require_docker
if /I "%ACTION%"=="reset" goto :require_docker
if /I "%ACTION%"=="restart" goto :require_docker
if /I "%ACTION%"=="start" goto :require_docker

echo [ERROR] Unknown command: %ACTION%
goto :help

:require_docker
if not exist "docker-compose.yml" (
  echo [ERROR] docker-compose.yml was not found.
  echo Run this file from the Construction OS repository root.
  exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
  echo [SETUP] Docker was not found. Attempting to install Docker Desktop...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Docker Desktop is required and Windows Package Manager ^(winget^) is unavailable.
    echo Install Docker Desktop once, then run start-local.cmd again.
    exit /b 1
  )

  winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo [ERROR] Docker Desktop installation did not complete successfully.
    exit /b 1
  )

  set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
)

where docker >nul 2>nul
if errorlevel 1 (
  set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
)

if /I "%ACTION%"=="stop" goto :stop
if /I "%ACTION%"=="logs" goto :logs
if /I "%ACTION%"=="reset" goto :reset

call :ensure_docker_running
if errorlevel 1 exit /b 1

docker compose version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker Compose is not available with this Docker installation.
  exit /b 1
)

if /I "%ACTION%"=="restart" goto :restart
goto :start

:ensure_docker_running
docker info >nul 2>nul
if not errorlevel 1 exit /b 0

echo [SETUP] Docker Desktop is not running. Starting it...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
  start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else (
  echo [ERROR] Docker Desktop executable was not found.
  exit /b 1
)

set /a DOCKER_TRIES=0
:wait_docker
set /a DOCKER_TRIES+=1
docker info >nul 2>nul
if not errorlevel 1 (
  echo [OK] Docker is ready.
  exit /b 0
)
if !DOCKER_TRIES! GEQ 90 (
  echo [ERROR] Docker Desktop did not become ready.
  echo Open Docker Desktop, finish any first-run setup it requests, then run this file again.
  exit /b 1
)
>nul 2>&1 timeout /t 2 /nobreak
if errorlevel 1 >nul 2>&1 ping 127.0.0.1 -n 3
goto :wait_docker

:prepare_env
if not exist ".env" (
  if not exist ".env.example" (
    echo [ERROR] .env.example is missing.
    exit /b 1
  )
  copy /y ".env.example" ".env" >nul
  echo [SETUP] Created .env from .env.example.
) else (
  echo [OK] Existing .env preserved.
)
exit /b 0

:start
call :prepare_env
if errorlevel 1 exit /b 1

echo.
echo ========================================
echo   Starting Construction OS locally
echo ========================================
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "CURRENT_BRANCH=%%B"
if defined CURRENT_BRANCH echo [INFO] Git branch: !CURRENT_BRANCH!

echo [SETUP] Building/updating containers and application dependencies...
docker compose up -d --build --remove-orphans
if errorlevel 1 (
  echo [ERROR] Construction OS failed to start.
  echo Run: start-local.cmd logs
  exit /b 1
)

echo [SETUP] Waiting for API and database migrations...
call :wait_url "http://localhost:8000/health" "API"
if errorlevel 1 goto :startup_failed

echo [SETUP] Waiting for web application...
call :wait_url "http://localhost:3000" "Web"
if errorlevel 1 goto :startup_failed

echo.
echo ========================================
echo   Construction OS is ready
echo ========================================
echo Web:      http://localhost:3000
echo API:      http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Useful commands:
echo   start-local.cmd logs
echo   start-local.cmd restart
echo   start-local.cmd stop
echo   start-local.cmd reset

echo [INFO] Opening Construction OS in your default browser...
start "" "http://localhost:3000"
exit /b 0

:wait_url
set "WAIT_URL=%~1"
set "WAIT_NAME=%~2"
set /a URL_TRIES=0
:wait_url_loop
set /a URL_TRIES+=1
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Uri '%WAIT_URL%' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
  echo [OK] %WAIT_NAME% is ready.
  exit /b 0
)
if !URL_TRIES! GEQ 90 (
  echo [ERROR] %WAIT_NAME% did not become reachable at %WAIT_URL%.
  exit /b 1
)
>nul 2>&1 timeout /t 2 /nobreak
if errorlevel 1 >nul 2>&1 ping 127.0.0.1 -n 3
goto :wait_url_loop

:startup_failed
echo.
echo [ERROR] Local startup did not complete successfully.
echo Showing recent container output:
docker compose ps
docker compose logs --tail=80
exit /b 1

:stop
call :ensure_docker_running
if errorlevel 1 exit /b 1
echo [INFO] Stopping Construction OS...
docker compose down --remove-orphans
exit /b %errorlevel%

:restart
call :prepare_env
if errorlevel 1 exit /b 1
echo [INFO] Restarting Construction OS...
docker compose down --remove-orphans
if errorlevel 1 exit /b 1
goto :start

:logs
call :ensure_docker_running
if errorlevel 1 exit /b 1
docker compose logs -f --tail=150
exit /b %errorlevel%

:reset
call :ensure_docker_running
if errorlevel 1 exit /b 1
echo.
echo WARNING: RESET deletes the LOCAL PostgreSQL data volume and local Docker state.
echo Repository source files are not deleted.
set /p "CONFIRM=Type RESET to continue: "
if /I not "%CONFIRM%"=="RESET" (
  echo Reset cancelled.
  exit /b 0
)
docker compose down -v --remove-orphans
if errorlevel 1 exit /b 1
echo [OK] Local data was reset. Run start-local.cmd to create a clean environment.
exit /b 0

:help
echo Construction OS local launcher
echo.
echo Usage:
echo   start-local.cmd          Start/build the full local stack and open the browser
echo   start-local.cmd restart  Restart the local stack
echo   start-local.cmd logs     Follow API/web/database logs
echo   start-local.cmd stop     Stop local containers without deleting data
echo   start-local.cmd reset    Stop and delete LOCAL database/container volumes
echo   start-local.cmd help     Show this help
exit /b 0
