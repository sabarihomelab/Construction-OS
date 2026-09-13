# Construction OS Architecture

## Product boundary

Construction OS is an **India-first standalone construction operating system**. Release 1 workflows, terminology, commercial priorities and compliance boundaries come from Indian contractor practice rather than a foreign product feature model.

Third-party products may be studied only as technical references or connected through explicit adapters. Core product operation never depends on another construction/accounting platform being available.

## Architecture principles

1. **India domain-first** — construction concepts live in canonical internal domain models grounded in Indian contractor workflows, not vendor payloads or UI state.
2. **Modular monolith first** — one deployable backend and one primary database initially, with strict module boundaries and an event/outbox spine. Runtime/worker separation happens only for proven deployment or scaling needs.
3. **Tenant isolation by design** — every business record is organization-owned. Even though commercial production deployment is currently planned as a dedicated customer environment, tenant context remains mandatory at API, service, database, cache, file, job, search, reporting and AI boundaries.
4. **Policy-driven authorization** — authentication identifies a subject; authorization evaluates organization membership, role, project scope, resource ownership and action.
5. **Auditability** — privileged and commercially meaningful actions produce audit/history with actor, tenant, resource, action, timestamp and correlation.
6. **Privacy-first** — core workflows do not require third-party analytics or AI. Sensitive data is minimized in logs, exports and integrations.
7. **AI as an optional evidence layer** — disabling AI leaves Construction OS fully functional. Models receive only authorized/minimized evidence and never become the authoritative business engine.
8. **No placeholder features** — code alone does not make a feature complete; persistence, validation, security, history, tests, documentation and usable UX are required.
9. **Enter once, reuse downstream** — authoritative field/procurement/commercial facts are referenced or projected rather than independently re-entered in multiple modules.
10. **India-specific without architectural lock-in** — jurisdiction-specific tax, withholding, localization and accounting integration live behind configurable/effective-dated rules and adapters rather than contaminating generic platform primitives.

## India-first capability domains

```text
Construction OS
├── Platform Core
│   ├── Organization / project scope
│   ├── Identity, MFA and sessions
│   ├── Roles, policies and project access
│   ├── Configuration, metadata and workflows
│   ├── Audit, notifications and events
│   └── Files, search, reporting, offline and integrations
├── Project Control
│   ├── Projects / sites
│   ├── Party / Business Directory
│   ├── WBS / Cost Codes
│   ├── BOQ
│   ├── Estimate / Rate Analysis / Budget
│   └── Basic planning / scheduling / lookahead
├── Field Execution
│   ├── Workforce / contract labour / crews
│   ├── Attendance
│   ├── Work quantities / daily progress / DPR
│   ├── Material received / used / requested
│   ├── Equipment usage
│   ├── Photos / issues
│   └── Quality / Safety / Punch
├── Procurement and Stores
│   ├── Material Master
│   ├── Indent / Material Requirement
│   ├── RFQ / Vendor Quote / Comparison
│   ├── Purchase Order
│   ├── Delivery Challan / GRN
│   └── Site/Store inventory transactions
├── Contracts and Commercial Control
│   ├── Subcontract / Work Order
│   ├── Measurement / Certification
│   ├── Subcontractor RA Billing
│   ├── Client Contract / RA Billing
│   ├── Receivable / payment status
│   ├── Job Cost / forecast / variance
│   └── India tax / withholding / invoice metadata
├── Project Information
│   ├── Documents / Drawings
│   ├── RFIs / Submittals
│   └── Meetings / correspondence
├── Accounting Integration
│   ├── Controlled Excel / CSV import-export
│   ├── Accounting integration contract
│   └── TallyPrime adapter priority
├── Support and Knowledge
│   ├── End-user help
│   ├── India product/module guidance
│   ├── Release / upgrade documentation
│   └── Diagnostics
└── Intelligence Layer
    ├── Permission-scoped Construction OS Assistant
    ├── Product/help/upgrade RAG
    ├── Future evidence-based project Q&A
    ├── Document extraction
    └── Risk/anomaly assistance
```

## Runtime structure

```text
apps/web                 Next.js web application
apps/api                 FastAPI application
apps/api/app/modules     bounded platform/business modules
packages/                shared contracts and reusable UI/runtime packages
infra/                   local and deployment infrastructure definitions
docs/                    architecture, India product, security and support documentation
```

PostgreSQL is the transactional source of truth. File bytes are stored through the storage-provider abstraction. Background work uses durable jobs/outbox events rather than depending on long HTTP requests.

## Data ownership and isolation

All customer business tables carry an organization identifier or are reachable only through an organization-owned aggregate. Application services never accept organization identity from an untrusted payload when it can be derived from the authenticated session.

Project-scoped data additionally enforces project ownership/permissions. Database row-level security remains a defense-in-depth target rather than a replacement for application authorization. Files, exports, caches, search, jobs, reporting, offline packages and AI context preserve the same boundary.

## Deployment model

The current commercial model is **one customer environment per Construction OS production installation**. The environment may run:

- on the customer's own server/on-premises infrastructure;
- on dedicated cloud infrastructure;
- as a small all-in-one deployment;
- with application, PostgreSQL, storage and heavy workers separated as scale requires.

The code remains tenant-safe internally, but Release 1 does not depend on hosting unrelated companies in one shared runtime/database.

Deployment composition is separate from business configuration:

`Infrastructure → installed/runtime modules → company configuration → project configuration → user experience`

## Accounting boundary

Construction OS owns construction operational and commercial truth: WBS, BOQ, budget, procurement, commitments, inventory, labour, equipment, subcontract, measurement, RA billing, client billing and job cost.

Release 1 does **not** attempt to recreate a complete Indian General Ledger/payroll/statutory accounting suite. Accounting systems remain the book of record where required, connected through adapters. Controlled Excel/CSV is the first adoption surface and TallyPrime is the initial accounting-integration priority.

## India compliance boundary

GST, TDS/withholding and e-invoice concepts are modeled through jurisdiction-aware, versioned/effective-dated rules and transaction snapshots where historical reproducibility requires them.

Never hardcode current statutory percentages, thresholds or section identifiers into permanent business logic. Full GST return filing and full payroll statutory processing are not pre-demo requirements.

## Third-party systems

External systems are optional edges. Integration adapters translate between canonical Construction OS objects and approved external systems. Connector failures must not corrupt authoritative Construction OS domain data.

## AI boundary

Construction OS Assistant never connects directly to unrestricted database data. Application services retrieve permission-scoped product/company evidence, construct bounded context and call a configured local/on-prem or approved cloud provider.

The Assistant may explain product behavior, configuration, release changes and upgrade/rollback procedures. It never silently executes migrations/upgrades and never authoritatively decides measurement, certification, RA billing, GST/TDS, payment, budget, safety closure or approvals.

See `docs/architecture/IN_APP_ASSISTANT_RAG.md`.
