# Construction OS

Construction OS is an all-in-one construction operations platform combining field reporting, project management, financial controls, accounting integrations, and AI-assisted workflows.

## Current foundation

- `apps/web` — Next.js web application
- `apps/api` — FastAPI backend
- PostgreSQL — primary application database
- Docker Compose — complete local development stack
- GitHub Actions — build/lint/test validation
- `docs/ARCHITECTURE.md` — product and technical boundaries

## One-click local development on Windows

After cloning the repository and switching to the branch you want to test, run:

```bat
start-local.cmd
```

That launcher handles the local development stack for you:

- checks for Docker
- attempts to install Docker Desktop through `winget` when Docker is missing
- starts Docker Desktop when needed
- creates `.env` from `.env.example` on the first run
- builds/updates the API and web containers
- installs Python and Node application dependencies inside Docker
- starts PostgreSQL
- waits for PostgreSQL health
- runs all Alembic database migrations automatically
- starts the FastAPI development server with reload enabled
- starts the Next.js development server
- waits until the API and web app are reachable
- opens `http://localhost:3000` in the default browser

You do not need to manually create a Python virtual environment, run `pip install`, install PostgreSQL, run Alembic, or run `npm install` on the host machine.

### Launcher commands

```bat
start-local.cmd
start-local.cmd restart
start-local.cmd logs
start-local.cmd stop
start-local.cmd reset
start-local.cmd help
```

`reset` deletes only the local Docker database/container volumes after explicit confirmation. It does not delete repository source files.

### Local addresses

- Web application: `http://localhost:3000`
- API: `http://localhost:8000`
- API health: `http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

## Manual development setup

The one-click launcher is the preferred workflow. Manual setup is still available for debugging individual services.

### Database only

```bash
docker compose up -d postgres
```

### API without Docker

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

### Web without Docker

```bash
cd apps/web
npm install
npm run dev
```

## Product direction

Construction OS grows through common platform services and construction domain modules rather than isolated screens. The current branch includes the shared platform foundation for tenancy, authorization, configuration, workflows, files, realtime/offline behavior, search, reporting, governance and related services. Future construction modules plug into those common services instead of rebuilding them independently.
