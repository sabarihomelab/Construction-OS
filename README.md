# Construction OS

Construction OS is an all-in-one construction operations platform combining field reporting, project management, financial controls, accounting integrations, and AI-assisted workflows.

## Current foundation

- `apps/web` — Next.js web application
- `apps/api` — FastAPI backend
- PostgreSQL — primary application database
- PowerShell — native Windows setup, maintenance and local-development workflow
- Docker Compose — retained as an optional infrastructure/deployment path for later use
- GitHub Actions — build/lint/test validation
- `docs/ARCHITECTURE.md` — product and technical boundaries
- `docs/operations/INSTALLATION-LIFECYCLE.md` — installation/module/upgrade safety contract

## Windows setup and maintenance

Run the operator-facing setup from the Construction OS installation/repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

On a first run, setup collects the environment name/type, deployment profile, local or external PostgreSQL mode, browser/API URLs and the business modules to activate. Module choices come from the same runtime manifest used by the application, and required dependencies are resolved automatically.

On an existing installation, rerunning the same command presents maintenance actions including:

- add business modules that are available in the current release but not yet installed;
- upgrade/refresh the installed version;
- reconfigure runtime/environment settings;
- repair dependencies;
- validate the installation.

Existing-install migration paths require a verified database backup/snapshot before migration. Successful actions are recorded without secrets under `.construction-os/install-state.json`.

`setup-local.ps1` is the lower-level native dependency/database bootstrap used by `setup.ps1`. It remains useful for development/debugging and scripted setup but is not the normal operator-facing entry point.

### Native dependencies

The low-level setup can:

- install Python 3.12 through `winget` when missing;
- install Node.js LTS/npm through `winget` when missing;
- install/start PostgreSQL for local database mode;
- connect to an existing PostgreSQL endpoint for external database mode without controlling that server;
- create `.env` from `.env.example`;
- create `apps/api/.venv`;
- install/update API and Web dependencies;
- apply the common Alembic database migration chain.

For a local development database, PostgreSQL installation may ask for the administrator password required to create the `construction` user/database. That administrator password is not persisted by Construction OS.

### Start Construction OS

After setup, start the application with:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

The current start script is a native development/demo launcher. It applies pending migrations, starts the FastAPI API and Next.js development server, waits for readiness, and opens the application.

Production packaging still requires Windows service registration, reverse proxy/TLS, managed secrets and versioned release-package staging/swap as documented in `docs/operations/INSTALLATION-LIFECYCLE.md`.

### Local addresses

Default local-development addresses are:

- Web application: `http://localhost:3000`
- API: `http://localhost:8000`
- API liveness: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/health/ready`
- API documentation: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

To stop local development, close the API and Web PowerShell windows, or press `Ctrl+C` in each window.

## Manual development setup

The PowerShell scripts are the preferred Windows workflow. Individual services can still be run manually for debugging.

### API

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Web

```powershell
cd apps/web
npm run dev
```

## Product direction

Construction OS grows through common platform services and construction domain modules rather than isolated screens. The current branch includes the shared platform foundation for tenancy, authorization, configuration, workflows, files, realtime/offline behavior, search, reporting, governance and related services. Future construction modules plug into those common services instead of rebuilding them independently.
