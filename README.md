# Construction OS

Construction OS is an **India-first construction operating platform** for small and mid-sized civil/general contractors, builders, MEP contractors and specialty subcontractors.

The product goal is one connected project operating system across BOQ, WBS/cost control, workforce, DPR, procurement, materials, equipment, measurement, RA billing, job cost, reporting and accounting integration.

> Complex underneath. Simple on top.

Foreign construction products may be studied as technical/product references, but US/UK workflows, terminology, accounting and compliance do **not** define Construction OS Release 1 priorities.

See:

- `docs/product/INDIA-FIRST-PRODUCT-CONTRACT.md` — current product contract
- `docs/product/INDIA-REFIT-GAP-ASSESSMENT.md` — keep/modify/deprioritize/new classification of the current repo
- `docs/product/RELEASE-REQUIREMENTS-BASELINE.md` — India Demo Build acceptance baseline
- `docs/architecture/IN_APP_ASSISTANT_RAG.md` — in-app support/upgrade AI boundary

## Current foundation

- `apps/web` — Next.js web application
- `apps/api` — FastAPI backend
- PostgreSQL — primary application database
- PowerShell — native Windows setup, maintenance and local-development workflow
- Docker Compose — optional infrastructure/deployment path
- GitHub Actions — build/lint/test validation
- shared platform services for authorization, configuration, metadata, workflows, files, audit, notifications, search, realtime/offline, reporting, integrations, governance, help and diagnostics

Existing Projects, Documents/Drawings, RFIs/Submittals, Daily Reports, Workforce, Safety/Inspections/Punch, Equipment/Materials and Meetings foundations are preserved. Their priorities and relationships are being refit around the India contractor workflow rather than rewritten from scratch.

## India Demo Build target

The first meaningful customer demonstration should coherently support a realistic persisted flow:

`Company → Project → Party → WBS/Cost Codes → BOQ → Estimate/Rate Analysis → Budget → Workforce/Attendance → DPR → Material Requirement → Approval → RFQ → Quotes → Comparison → PO → GRN → Site Inventory → Material Consumption → Equipment Usage → Measurement → Subcontract Work Order → Subcontractor RA Bill → Client RA Bill → Job Cost → Dashboard/Reports → Excel/Tally bridge → Closeout basics`

Release 1 is **not** a full replacement for Tally, Primavera/MS Project, AutoCAD/BIM tools, payroll statutory systems or GST-return filing software.

## India defaults

New company setup defaults to:

- country: India (`IN`)
- locale: `en-IN`
- timezone: `Asia/Kolkata`
- base currency: `INR`
- unit system: metric

These are defaults, not hard global restrictions. Existing stored organization/project settings are preserved and the underlying architecture remains localization-capable.

## Windows setup and maintenance

Run the operator-facing setup from the Construction OS installation/repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

On first run, setup collects environment/deployment/database settings and the business modules to activate. Module choices come from the same runtime manifest used by the application, and required dependencies are resolved automatically.

On an existing installation, rerunning the same command supports adding newly available modules, upgrade/refresh, reconfiguration, dependency repair and validation. Existing-install migrations require a verified database backup/snapshot before migration. Successful actions are recorded without secrets under `.construction-os/install-state.json`.

`setup-local.ps1` is the lower-level native bootstrap used by `setup.ps1`.

### Start Construction OS

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

Default development addresses:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- Readiness: `http://localhost:8000/health/ready`
- API docs: `http://localhost:8000/docs`

## In-app Construction OS Assistant

Construction OS is being prepared for an optional in-app, evidence-based assistant. Its first role is product help, configuration explanation, release notes, installation/upgrade readiness and rollback guidance using retrieval-augmented context.

The assistant is **not an authoritative business engine**. It must never silently perform migrations/upgrades or decide measurement, billing, GST/TDS, payment, budget, certification, safety closure or approvals. Deterministic services and explicit users remain authoritative.

The assistant is provider-pluggable so a deployment may later choose a local/on-prem model or an approved cloud model without changing business modules.

## Development direction

Major new business development now follows the India dependency path, beginning with Party / Business Directory, WBS / Cost Codes and BOQ before deeper commercial execution modules.

Every module must reuse shared platform services and preserve tenant/project security, history, configuration, audit, search/reporting, offline behavior where applicable and additive migration safety.
