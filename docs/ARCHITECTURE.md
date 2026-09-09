# Construction OS Architecture

## Product boundary

Construction OS is designed as a multi-tenant construction operating system with four primary capability groups:

1. **Field Operations** — crews, time, daily reports, photos, equipment, safety and production.
2. **Project Management** — projects, tasks, drawings, RFIs, submittals, documents, inspections and schedules.
3. **Commercial & Finance** — cost codes, budgets, commitments, change orders, expenses, job costing, billing and payroll preparation.
4. **Platform & Intelligence** — identity, permissions, audit, integrations, notifications, reporting and AI assistance.

## Initial architecture

We start as a modular monolith rather than microservices. This keeps local development, transactions and deployments simple while preserving module boundaries that can be extracted later.

```text
apps/web       Next.js user interface
apps/api       FastAPI application
packages/      shared contracts/components added as needed
infra/         deployment/infrastructure definitions
```

PostgreSQL is the source of truth. External systems such as Procore and Sage are accessed only through connector modules. Domain code must not depend directly on vendor-specific payloads.

## Multi-tenancy

Every business record belongs to an `organization_id`. Authorization is evaluated using organization membership plus project-level permissions. Future database row-level security can reinforce application-level checks.

## Integration rule

Internal canonical models are stable. Connectors translate between canonical models and vendor models:

```text
Construction OS domain <-> Connector <-> Procore / Sage / other provider
```

This prevents external API changes from leaking throughout the product.
