# Construction OS Business Logic Source of Truth

## Purpose

This document defines where Construction OS business rules live, how they are documented, how they are enforced, and how web/mobile clients must consume them.

The repository itself must be the durable source of truth. Product behavior must not depend on old chat history, developer memory, UI assumptions, or undocumented conventions.

## Core principle

Construction OS separates four responsibilities:

1. **Product / module contracts define what the business means and what the system must do.**
2. **Backend services enforce business truth, permissions, workflow, calculations, historical integrity and tenant/project isolation.**
3. **API contracts expose approved capabilities and state to clients.**
4. **Web and Android clients present those capabilities quickly and safely; they must not become a second source of business logic.**

The client may guide the user, hide unavailable controls and provide optimistic local UX, but the backend remains authoritative.

## Documentation hierarchy

### 1. Release baseline — overall product scope

Primary document:

`docs/product/RELEASE-REQUIREMENTS-BASELINE.md`

Defines what the India-first Construction OS Release 1 must accomplish end-to-end.

Examples:

- Company and project setup
- Party / client / vendor / subcontractor setup
- WBS / Cost Codes
- BOQ
- Estimate / Rate Analysis / Budget
- Workforce / Attendance
- DPR
- Procurement / RFQ / quotations / PO / GRN
- Inventory / material usage
- Equipment
- Safety / quality
- Measurement and certification
- Subcontract RA billing
- Scheduling
- Job Cost
- Client billing / receivables
- India tax / withholding architecture
- Tally / accounting interoperability
- Dashboards / reports
- Closeout
- Android field workflow and offline support

This document answers: **What must the whole product achieve?**

### 2. India-first product contract — cross-module business principles

Primary document:

`docs/product/INDIA-FIRST-PRODUCT-CONTRACT.md`

Defines shared domain rules that should remain consistent across modules.

Examples:

- WBS / Cost Codes are internal project-control structures and are not BOQ.
- BOQ is contractual quantity/rate/billing scope.
- Worker is not User.
- Party is shared across client/vendor/supplier/subcontractor roles.
- Quantities and money use authoritative Decimal/Numeric values.
- Inventory is transaction-derived rather than a manually edited balance.
- RA billing is cumulative.
- Tax and withholding rules are versioned/effective-dated rather than permanently hardcoded.
- Construction OS owns construction-commercial truth while statutory accounting remains adapter-driven.

This document answers: **What principles apply across the whole Construction OS domain?**

### 3. Module Contract — required specification format for every module

Primary document:

`docs/product/MODULE-CONTRACT.md`

Every business or platform module must eventually maintain one complete module contract.

Each module contract must document at minimum:

- module identity and purpose;
- business terminology;
- system/admin/business objects;
- object relationships;
- page/screen inventory;
- permissions and scopes;
- workflow states and transitions;
- validation and business rules;
- calculations and derived values;
- schema and indexing expectations;
- historical/immutability rules;
- compatibility/migration behavior;
- security/privacy;
- audit events;
- notifications;
- realtime/offline/client-state behavior;
- performance budgets;
- import/export/reporting behavior;
- known exclusions and future scope.

This document answers: **How must one module be specified so implementation, support and future client work stay consistent?**

### 4. Module-specific product documents — actual business rules

Current examples under `docs/product/` include:

- `PROJECTS.md`
- `WBS-COST-CODES.md`
- `BOQ.md`
- `ESTIMATING-RATE-ANALYSIS-BUDGET.md`
- `WORKFORCE-TIME.md`
- `DAILY-REPORTS.md`
- `FINANCIALS-JOB-COST.md`
- `RFI-MODULE.md`
- `DOCUMENTS-SPECIFICATIONS.md`
- `DRAWINGS.md`
- `ACCESS-MODEL.md`

These contain actual module-level business meaning and rules.

They should progressively be normalized into the complete Module Contract structure rather than remaining inconsistent standalone notes.

### 5. Backend implementation — authoritative enforcement

Backend code under `apps/api/app/modules/` enforces business logic.

Examples of rules that must be enforced server-side:

- approved BOQ cannot be silently edited;
- only valid project WBS references may be used;
- approved attendance is historical evidence;
- DPR approval/report issuance must follow workflow and permissions;
- sensitive worker rates require dedicated permissions;
- project/organization isolation is enforced on every request;
- financial calculations are server-side;
- stale revisions are rejected with conflict handling;
- duplicate retries are idempotent where required;
- historical approved/certified/posted values preserve applied rules.

A UI control being hidden or disabled is never the security or business-rule boundary.

### 6. API / frontend integration contracts

Primary current document:

`docs/product/FRONTEND-INTEGRATION-MODULES-1-6.md`

Defines the stable integration surface between backend and clients for released modules.

It documents:

- canonical API roots;
- project/organization scoping;
- permissions;
- optimistic concurrency;
- HTTP 403 / 409 / 422 behavior;
- workflow boundaries;
- report generation state;
- historical records;
- client integration expectations.

This document answers: **How may a client consume the business capability without reproducing backend logic?**

### 7. Android implementation instructions

Primary document:

`docs/mobile/ANDROID-APP-WORK-INSTRUCTION.md`

This is an implementation guide for the Android client, not the source of construction business logic.

It defines:

- Kotlin / Jetpack Compose architecture;
- Room local database;
- WorkManager synchronization;
- mobile authentication/session fitting;
- secure local storage;
- permission-driven navigation;
- offline-first field workflows;
- performance targets;
- photo/media behavior;
- testing order;
- Android project layout.

Android must consume product/backend rules rather than inventing different ones.

## Authority model

Use this rule whenever implementation decisions are unclear:

```text
Business meaning
    ↓
Product / Module Contract
    ↓
Backend enforcement
    ↓
API contract
    ↓
Web / Android presentation
```

The direction must not be reversed.

A mobile screen must not introduce a new business rule simply because it is convenient for the UI.

## Example: BOQ

Business rule:

> An approved BOQ is immutable historical commercial evidence.

Where it belongs:

- BOQ module contract/product document defines the rule.
- Backend service rejects invalid edits.
- API exposes status/revision/history.
- Android/web render approved records as read-only.

If a modified APK enables an Edit button, the backend must still reject the edit.

## Example: Attendance

Business rule:

> Draft/rejected attendance may be edited according to permissions; approved attendance is governed historical evidence.

Where it belongs:

- Workforce/Attendance module contract defines the lifecycle.
- Backend enforces state/permission/revision rules.
- API exposes current state and allowed actions.
- Android gives immediate local UX but sync still passes through backend validation.

Offline storage improves responsiveness; it does not become authoritative business truth.

## Example: DPR

Business rule:

> DPR is structured project data; workforce/material/equipment/safety information should be reused from authoritative modules rather than duplicated where possible.

Where it belongs:

- DPR module/product contract defines ownership boundaries.
- DPR provider assembles normalized authoritative payload.
- Backend controls approval and official issue.
- Android captures DPR-owned field data and displays report-generation status.
- PDF/DOCX generation remains server-side.

## Required future module-contract library

The target structure is one standardized module contract for every major Construction OS bounded context.

Recommended structure:

```text
docs/modules/
├── company/MODULE.md
├── projects/MODULE.md
├── party/MODULE.md
├── wbs/MODULE.md
├── boq/MODULE.md
├── estimating/MODULE.md
├── workforce/MODULE.md
├── attendance/MODULE.md
├── dpr/MODULE.md
├── procurement/MODULE.md
├── inventory/MODULE.md
├── equipment/MODULE.md
├── safety/MODULE.md
├── quality/MODULE.md
├── subcontracts/MODULE.md
├── measurement/MODULE.md
├── ra-billing/MODULE.md
├── scheduling/MODULE.md
├── financials/MODULE.md
├── client-billing/MODULE.md
├── documents/MODULE.md
├── drawings/MODULE.md
├── rfis/MODULE.md
├── submittals/MODULE.md
├── reporting/MODULE.md
├── integrations/MODULE.md
└── platform/...
```

Not every one of these modules is currently complete. Documentation must distinguish:

- released and validated capability;
- implemented foundation;
- partial capability;
- planned capability;
- intentionally deferred capability.

Do not describe planned code as production-ready merely because models or folders exist.

## Standard questions every module must answer

Every future module contract must make these answers explicit:

1. What business problem does this module solve?
2. Who uses it?
3. What objects exist and which module owns each one?
4. What statuses/lifecycle states exist?
5. What transitions are allowed?
6. Who may perform each action?
7. Which calculations/validations happen?
8. Which values become immutable and when?
9. Which data comes from other authoritative modules?
10. What is duplicated only as a historical snapshot and why?
11. What is configurable at platform/company/project level?
12. What is effective-dated/versioned?
13. What happens when data changes after approval/certification/posting?
14. What gets audited?
15. What gets reported/exported?
16. What works offline?
17. How are retries/idempotency/conflicts handled?
18. What data may be cached on Android?
19. What must never be trusted from the client?
20. What performance/data-volume assumptions apply?
21. What is explicitly out of scope for the current release?

## Client rule

Web and Android may:

- hide unavailable actions based on access context;
- optimize interaction count;
- validate simple input early;
- cache permitted data;
- queue offline mutations;
- show optimistic local state;
- show sync/conflict/error status;
- format data for the user.

Web and Android must not be the only place that:

- authorizes an action;
- calculates authoritative money/tax/certification;
- decides final workflow validity;
- determines tenant/project access;
- makes approved history mutable;
- resolves business conflicts silently;
- defines statutory/commercial truth.

## Change rule

When a business rule changes:

1. update the relevant product/module contract;
2. determine historical-data/versioning impact;
3. update backend enforcement;
4. update API contract if required;
5. update web/mobile behavior;
6. update migrations/backfills if required;
7. add/update tests;
8. run CI;
9. only then call the behavior complete.

Do not change only the Android or web screen and assume the business rule changed.

## Current documentation status

Construction OS already has a strong overall product/release foundation and detailed documents for several modules, but the standardized per-module contract library is not yet complete for every business area.

The goal is therefore not to reinvent the product. The goal is to progressively consolidate existing product documents and implemented backend behavior into consistent module contracts so the repository itself remains the permanent reference for future development, support, Android/web work and new chat sessions.
