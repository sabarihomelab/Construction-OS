# Web Frontend Parity Plan

Status: ACTIVE DEVELOPMENT PRIORITY
Branch: `build/platform-foundation`

## Current priority

**Freeze new business-module expansion. Complete the web frontend for the backend capabilities that are already released/available first.**

Do not start the next major backend module until the Web Frontend Parity Checkpoint defined in this document is complete.

Read together with:
- `docs/engineering/AGENT-EXECUTION-POLICY.md`
- `docs/engineering/DEV-WORKS.txt`
- `docs/PRODUCT_DEFINITION_OF_DONE.md`

## Goal

The web application must become a complete, usable browser interface for the backend capabilities that are currently released for use.

A feature is not considered web-complete merely because:
- a route exists,
- a workspace renders,
- a backend endpoint exists,
- or a button is visually present.

The user must be able to complete the supported workflow from the web UI without manual API calls, database edits, hidden developer steps, or fake UI-only data.

## Scope rule

The backend feature registry is the release source of truth.

### Build now

Complete web parity for features with release state `AVAILABLE`, including their released child pages and supported actions.

Current available web-facing scope includes:
- Home / workspace shell
- Field / Daily Progress Reports
- DPR Templates
- Workforce & Time
- Attendance
- Party Directory
- WBS / Cost Codes
- Bill of Quantities
- Estimating / Rate Analysis / Budget
- Administration shell
- Company Settings
- Roles & Access
- Operations Center
- Help

Also preserve and complete the project-scoped released workflows already present in the web app, including project selection/access and existing commercial/financial workflow surfaces that are already backed by stable APIs.

### Do not expand yet

Do not build full new frontend products for features still marked `PLANNED` merely because backend foundation code exists.

Examples currently include:
- Projects full module UI
- Documents
- Drawings
- RFIs
- Submittals
- Meetings
- Safety
- Equipment / Materials full module
- Procurement
- Subcontracts
- Scheduling
- Financials full module
- Company Configuration
- Custom Fields
- Assistant

Existing foundations/routes for planned areas must not be deleted. They may be touched only when required by an available workflow or to prevent regressions.

After available web parity is complete, resume the Release 1 business-module roadmap and release each new module together with its web surface.

## Execution policy

Use `docs/engineering/AGENT-EXECUTION-POLICY.md`.

For this effort, each slice below is normally a **FEATURE** task:
- inspect only the relevant backend contract and existing frontend files,
- implement the missing web behavior,
- run targeted frontend/backend contract tests,
- do not run full repository CI after each slice,
- do not repeatedly run production frontend builds during normal iteration.

Run the full frontend production build and broader validation only at the Web Frontend Parity Checkpoint.

## Definition of web parity

For every in-scope feature, verify all applicable items:

1. Route is reachable from normal navigation when the user has permission.
2. Route is hidden or denied correctly when the user lacks permission.
3. List/read workflow uses real backend data.
4. Create workflow is available when backend supports creation.
5. Edit/update workflow is available when backend supports updates.
6. Detail view exposes the meaningful backend fields needed by the user.
7. State/workflow actions are exposed where supported, such as submit, approve, reject, reopen, certify, or generate.
8. Revision/history is visible where the backend maintains it and it is operationally relevant.
9. Validation errors are understandable in the UI.
10. Loading, empty, success and failure states are handled.
11. Project/organization context is preserved correctly.
12. Permission checks match the backend permission catalog.
13. UI never invents authoritative values that belong to the backend.
14. Refresh/reload does not lose authoritative state.
15. Important desktop layouts remain usable at practical laptop widths.
16. Existing mobile/field-specific behavior is not broken by web changes.
17. Targeted tests pass.

## Work slices

### WEB-00 — Shell, navigation and parity inventory

Purpose: make the web structure reliable before filling individual workflows.

Tasks:
- inventory current routes against the backend feature registry,
- inventory existing workspaces against stable backend API contracts,
- make available features discoverable through normal navigation,
- ensure planned features are not presented as completed products,
- preserve project switching and authenticated session context,
- preserve permission-aware navigation,
- standardize loading/error/empty states where practical,
- identify duplicate/legacy navigation patterns and converge carefully without breaking existing routes.

Targeted validation:
- web type check/lint if configured,
- session/navigation smoke checks,
- feature-registry/permission contract tests.

### WEB-01 — Administration parity

Scope:
- Company Settings
- Roles & Access
- Project Access where currently supported
- Operations Center

Tasks:
- complete missing actions and states,
- add the missing Operations Center route/UI backed by existing operational/deployment APIs,
- verify permission gating and audit-sensitive actions.

### WEB-02 — Party Directory parity

Tasks:
- list/search/filter,
- create/edit/detail,
- relevant project assignments,
- backend validation/error handling,
- permission-aware actions.

### WEB-03 — WBS / Cost Codes parity

Tasks:
- list/tree/detail,
- create/update hierarchy,
- parent/child handling,
- relevant status/workflow behavior,
- project-scoped routes and permissions.

### WEB-04 — BOQ parity

Tasks:
- BOQ list/detail,
- items,
- create/update where supported,
- approval,
- revisions/history,
- project/WBS linkage,
- validation and totals from authoritative backend values.

### WEB-05 — Estimating / Budget parity

Tasks:
- estimate list/detail/edit,
- estimate submit/approve,
- budget views,
- budget approval/revision behavior currently supported,
- rate-analysis surfaces currently supported by stable backend contracts,
- correct permission/state handling.

### WEB-06 — Workforce / Attendance parity

Tasks:
- workforce list/detail/assignment workflows currently supported,
- attendance list/register/detail,
- attendance create/update,
- submit/approve,
- history,
- practical bulk-entry UX where backend supports it,
- permission and project-context handling.

### WEB-07 — DPR / Reporting parity

Tasks:
- daily-report list/detail,
- create/update,
- structured work progress,
- submit/approve/review actions currently supported,
- report generation,
- render history,
- DPR Templates route and management UI,
- relevant photo/media behavior already supported by the backend,
- clear state and failure handling.

### WEB-08 — Existing commercial/project workflow cleanup

Purpose: close already-built backend/web gaps that sit around Modules 1–6 without opening new planned modules.

Tasks may include currently supported:
- commercial dashboard/control-room behavior,
- measurement surfaces,
- RA billing surfaces,
- vendor-bill surfaces,
- project-scoped deep links,
- consistent navigation between project-level and global routes.

Only expose behavior already supported by stable backend APIs. Do not use this slice to invent the future Measurement/Certification or Financials domain.

### WEB-09 — Help and usability hardening

Tasks:
- implement released Help route/content surface,
- remove dead controls,
- verify keyboard/form behavior,
- verify responsive desktop/laptop layouts,
- normalize confirmations, destructive-action affordances, errors and success feedback,
- verify browser refresh/deep-link behavior.

## Web Frontend Parity Checkpoint

Only after WEB-00 through WEB-09 applicable work is complete:

1. Run frontend production build.
2. Run frontend lint/type checks.
3. Run Modules 1–6 frontend contract tests.
4. Run targeted backend integration tests used by web workflows.
5. Smoke-test every available feature route.
6. Test create/edit/state actions with a full-access development admin.
7. Test representative restricted users for permission-aware visibility/actions.
8. Verify direct/deep URLs and browser refresh.
9. Verify no available feature points to a missing route.
10. Verify no important UI action depends on fake/local-only authoritative data.
11. Update `DEV-WORKS.txt` with the final parity status.

When all checks pass, record:

`WEB FRONTEND PARITY CHECKPOINT COMPLETE`

Only then resume major new Release 1 backend modules.

## Development order after parity

After the checkpoint, continue the India Release 1 critical path. New modules must no longer be developed backend-first for a long period. Each new module should be delivered in bounded slices with its required web surface included before the module is declared complete.

## Core rule

> Backend capability and web usability must move together. For now, catch the web up to the released backend before expanding the product further.
