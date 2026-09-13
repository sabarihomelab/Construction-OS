# Frontend Integration Contract — Modules 1–6

This document is the handoff contract between the Construction OS API and the web/mobile UI for the first six India-first modules.

## Shared integration rules

- The authenticated session determines the company. Client payloads must not supply `organization_id`.
- Project-scoped resources take `project_id` from the URL and enforce project membership/permissions server-side.
- Mutations use CSRF protection.
- Governed records use optimistic concurrency (`expected_revision` or the record-specific concurrency token). A stale write returns HTTP 409 and the UI must refresh before retrying.
- Validation/business-rule failures return HTTP 422 and should be shown as actionable form/workflow feedback.
- Permission failures return HTTP 403. The UI should hide unavailable actions, but the API remains authoritative.
- Historical/approved records are not silently rewritten. Revision/history endpoints are the source for audit views.
- Search indexing is asynchronous. The background worker is part of the default stack and processes the search jobs emitted by these modules.
- Deep links must use stable entity IDs, not list positions or display names.

## Module 1 — Company / Parties

Frontend surfaces:

- `/admin/company`
- `/commercial/parties`
- Party detail deep link

Canonical API roots:

- `GET/PATCH /api/v1/organization`
- `GET/PATCH /api/v1/organization/settings`
- `/api/v1/commercial/parties/{party_id}`
- `/api/v1/projects/{project_id}/commercial/party-assignments`
- `/api/v1/projects/{project_id}/commercial/party-assignments/{assignment_id}`

The company is the tenant authority. Party is the reusable client/vendor/supplier/subcontractor identity. Project Party Assignment supplies the project-specific relationship; the UI must not create duplicate Parties merely because the same company works on another project.

## Module 2 — WBS / Cost Codes

Frontend surface: `/commercial/wbs` plus project/entity deep links.

Canonical API roots:

- `GET/POST /api/v1/projects/{project_id}/commercial/wbs`
- `GET /api/v1/projects/{project_id}/commercial/wbs/tree`
- `GET/PATCH /api/v1/projects/{project_id}/commercial/wbs/{wbs_id}`

WBS is the internal project-control hierarchy. It is not the BOQ. There is no customer destructive-delete contract for WBS; lifecycle/status actions preserve historical references.

## Module 3 — Bill of Quantities

Frontend surface: `/commercial/boq` plus BOQ deep links.

Canonical API roots include:

- `GET/POST /api/v1/projects/{project_id}/commercial/boqs`
- `GET/PATCH /api/v1/projects/{project_id}/commercial/boqs/{boq_id}`
- BOQ item routes
- `/approve`
- `/cancel`
- `/revisions`
- `/import/preview`
- `/import/apply`
- `/export.csv`
- approved-revision CSV export
- import template CSV

BOQ is contractual quantity/rate scope. Approval creates immutable evidence. The UI must not treat an approved BOQ as editable current-state data; revision/history is authoritative.

## Module 4 — Estimate / Rate Analysis / Budget

Frontend surface: `/estimating` plus estimate and budget deep links.

Canonical workflow endpoints include:

- estimate detail
- copy approved BOQ scope into estimate
- rate analysis per estimate item
- estimate submit / approve / revise / approval history
- budget generation and approval / approval history

The UI must preserve the commercial boundary: BOQ selling/contract values are not automatically project cost. Rate analysis establishes internal cost; budget is generated from approved estimate evidence; profit is not project cost.

## Module 5 — Workforce / Contract Labour / Attendance

Frontend surface: `/workforce` plus attendance deep links.

Canonical attendance roots:

- `GET/POST /api/v1/projects/{project_id}/workforce/attendance`
- attendance detail
- bulk entries
- submit / approve / reject
- history
- DPR summary

Worker identity is company-level and separate from application User/login. Project Worker Assignment carries project-specific employer/crew/trade/engagement context. Attendance responses intentionally exclude sensitive commercial worker rates.

Approved attendance is the workforce source for DPR reporting. Attendance itself does not create a second labour-cost posting path.

## Module 6 — Daily Progress Report / Reporting

Frontend surfaces:

- `/field`
- DPR detail deep link
- `/field/dpr-templates`

Core DPR roots include:

- `GET/POST /api/v1/projects/{project_id}/daily-reports`
- DPR detail/update/sections
- work progress linked to WBS and/or approved BOQ
- submit / approve / reject / reopen / void
- DPR lifecycle history
- normalized report payload
- preview/render
- issued-render history
- exact issued-file download
- DPR templates, versions and publish
- `GET /api/v1/projects/{project_id}/daily-reports/{report_id}/report-generation`

### Official report generation

The DPR report type owns its own generation policy. The default official output is PDF and the default trigger is approval.

When a DPR becomes approved—either because approval is not required at submit time or because an approver approves it—the API transaction enqueues one idempotent issuance job for that exact DPR revision. The background worker generates and stores the official file without blocking the approval request.

The UI should poll `report-generation` after approval. `generation_state` is one of the report lifecycle states exposed by the backend, including `not_ready`, `not_queued`, queued/running/retrying/failed job states, and `issued`. When issued, the response provides the render ID, filename and download path.

An issued render pins the exact source revision, published template version, normalized payload snapshot, presentation snapshot, content hash, FileAsset and FileVersion. Later edits or template changes do not rewrite historical issued DPRs.

Uploaded Word templates are supported for DOCX/PDF issuance. The standard container image includes LibreOffice for deterministic Word-to-PDF conversion.

## Release-state rule

The following first-six-module surfaces are intentionally released independently:

- Company Settings
- Party Directory
- WBS / Cost Codes
- BOQ
- Estimating / Budget
- Workforce / Attendance
- DPR / DPR Templates

A released child surface does not imply that the entire parent Commercial or other later modules are complete. Do not expose planned parent features merely because these slices are available.

## Frontend definition of ready

A module is ready for frontend consumption only when its canonical API surface, permission keys, optimistic concurrency behavior, migration path, search/deep-link behavior, feature release state and contract tests all pass the repository CI gate. The cumulative Modules 1–6 contract test protects those integration roots in addition to each module's own focused test suite.
