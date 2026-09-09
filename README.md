# Construction OS

Construction OS is an all-in-one construction operations platform combining field reporting, project management, financial controls, accounting integrations, and AI-assisted workflows.

## Current foundation

- `apps/web` — Next.js web application
- `apps/api` — FastAPI backend
- PostgreSQL — primary application database
- Docker — local service setup
- GitHub Actions — build/lint validation
- `docs/ARCHITECTURE.md` — product and technical boundaries

The first domain slice already includes a Project model plus list/create API endpoints. Future modules will follow the same bounded-module structure.

## Local setup

### 1. Database

```bash
docker compose up -d postgres
```

### 2. API

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

API health check: `http://localhost:8000/health`
API documentation: `http://localhost:8000/docs`

### 3. Web

```bash
cd apps/web
npm install
npm run dev
```

Web application: `http://localhost:3000`

## Product direction

Construction OS will grow through modules rather than isolated screens:

- Field operations
- Project management
- Drawings, RFIs and submittals
- Scheduling and workforce
- Safety and inspections
- Equipment and materials
- Budgets and job costing
- Commitments and change orders
- Billing and payroll preparation
- Procore and Sage connectors
- Reporting, audit and permissions
- AI-assisted field and office workflows

See `docs/ARCHITECTURE.md` for architectural rules.
