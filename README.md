# Construction OS

Construction OS is an all-in-one construction operations platform combining field reporting, project management, financial controls, accounting integrations, and AI-assisted workflows.

## Current foundation

- `apps/web` — Next.js web application
- `apps/api` — FastAPI backend
- PostgreSQL — primary application database
- PowerShell — preferred native Windows local-development workflow
- Docker Compose — retained as an optional infrastructure/deployment path for later use
- GitHub Actions — build/lint/test validation
- `docs/ARCHITECTURE.md` — product and technical boundaries

## Local development on Windows — no Docker required

After cloning the repository and switching to the branch you want to test, run the setup once from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-local.ps1
```

The setup script:

- installs Python 3.12 through `winget` when missing
- installs Node.js LTS/npm through `winget` when missing
- installs PostgreSQL 17 through `winget` when missing
- starts the local PostgreSQL Windows service
- creates the local `construction` database user and `construction_os` database when needed
- creates `.env` from `.env.example`
- creates `apps/api/.venv`
- installs/updates FastAPI/Python dependencies
- installs/updates Next.js/Node dependencies
- applies Alembic database migrations

PostgreSQL installation may ask you to choose an administrator password. The setup script asks for that password once when it needs to create the Construction OS development database. The password is not written to the repository.

### Start Construction OS

After setup, start the application with:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

The start script:

- makes sure PostgreSQL is running
- applies any newly added migrations
- starts the FastAPI API in its own PowerShell window
- starts the Next.js development server in its own PowerShell window
- waits for both services
- opens the application in your default browser

### Local addresses

- Web application: `http://localhost:3000`
- API: `http://localhost:8000`
- API health: `http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

To stop development, close the API and Web PowerShell windows, or press `Ctrl+C` in each window.

If dependencies change after pulling new code, run `setup-local.ps1` again. It is safe to rerun and keeps the existing local `.env` and database.

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
