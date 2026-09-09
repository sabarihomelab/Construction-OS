# Construction OS Architecture

## Product boundary

Construction OS is a standalone construction operating system. It is not a runtime wrapper around Procore, Raken, Sage, or any other construction/accounting product. Existing products are capability benchmarks only. Construction OS owns its workflows and data model natively.

Future import/migration adapters may read legacy data from third-party systems, but core product operation must never depend on those systems being available.

## Architecture principles

1. **Domain-first** — construction concepts live in internal domain models, not vendor payloads or UI state.
2. **Modular monolith first** — one deployable backend and one primary database initially, with strict module boundaries and an event/outbox spine. Modules can be extracted later without redesigning the product.
3. **Tenant isolation by design** — every business record is tenant-owned. Tenant context is mandatory at the API, service, database, cache, file, job, search, reporting and AI boundaries.
4. **Policy-driven authorization** — authentication identifies a subject; authorization evaluates organization membership, role, project scope, resource ownership and action.
5. **Auditability** — privileged and financially meaningful actions produce immutable audit events with actor, tenant, resource, action, timestamp and correlation id.
6. **Privacy-first** — core workflows do not require third-party analytics or AI. Sensitive data is minimized in logs, exports and integrations.
7. **AI as an optional layer** — AI requests pass only through the internal AI gateway. Disabling AI must leave the application fully functional.
8. **No placeholder features** — a feature is not considered implemented until its real workflow, persistence, permissions, validation, audit behavior, error states, tests and documentation exist.

## Capability domains

```text
Construction OS
├── Platform Core
│   ├── Organizations and tenancy
│   ├── Identity, MFA and sessions
│   ├── Roles, policies and project access
│   ├── Audit, notifications and workflow approvals
│   └── Files, search, reporting and configuration
├── Project Delivery
│   ├── Projects, directory and contacts
│   ├── Tasks, schedules and milestones
│   ├── RFIs, submittals and correspondence
│   ├── Drawings, specifications and documents
│   ├── Inspections, punch and observations
│   └── Bids, contracts and change control
├── Field Operations
│   ├── Daily logs and progress
│   ├── Time, crews and attendance
│   ├── Photos, notes and weather records
│   ├── Production quantities
│   ├── Equipment and materials
│   └── Safety, toolbox talks and incidents
├── Commercial and Finance
│   ├── Cost codes and chart of accounts
│   ├── Estimates, budgets and forecasts
│   ├── Commitments and purchase orders
│   ├── Job costing and WIP
│   ├── AP, AR, billing and cash
│   ├── Payroll and labor costing
│   └── General ledger and financial reporting
├── Support and Knowledge
│   ├── End-user help center
│   ├── Admin documentation
│   ├── API/developer documentation
│   ├── Release notes and status
│   └── Support requests and diagnostics
└── Intelligence Layer
    ├── AI gateway and policy enforcement
    ├── Search and question answering
    ├── Document extraction
    ├── Drafting and summarization
    └── Risk/anomaly assistance
```

## Runtime structure

```text
apps/web                 Next.js web application
apps/api                 FastAPI application
apps/api/app/modules     bounded business modules
packages/                shared contracts and reusable UI/runtime packages
infra/                   local and deployment infrastructure definitions
docs/                    architecture, security, product and support documentation
```

PostgreSQL is the transactional source of truth. Object/file content is stored through a storage abstraction. Background work uses durable jobs/outbox events rather than relying on HTTP requests to finish long-running work.

## Data ownership and isolation

All tenant business tables carry an organization identifier or are reachable only through a tenant-owned aggregate. Application services never accept tenant identity from an untrusted payload when it can be derived from the authenticated session.

Database row-level security is a defense-in-depth target for tenant-owned data, not a replacement for application authorization. Files, exports, caches, search indexes, background jobs and AI requests must preserve the same tenant boundary.

## Deployment model

The architecture supports both:

- **Managed SaaS** — logically isolated tenants with strong authorization, encryption and tenant-aware storage.
- **Private deployment** — a dedicated application/database/storage boundary for a single customer where contractual or regulatory requirements require stronger infrastructure isolation.

## Third-party systems

External products are optional edges, not dependencies. Future migration adapters may import historical data from legacy construction/accounting systems. Optional integration adapters may also be added where customers explicitly need them, but Construction OS retains its own canonical models and remains operational without those providers.

## AI boundary

AI never connects directly to the database. The AI gateway receives an authorized, minimized context prepared by application services. Tenant admins can disable AI globally or by feature. Secrets, authentication tokens and unrestricted database/file access are never supplied to models.
