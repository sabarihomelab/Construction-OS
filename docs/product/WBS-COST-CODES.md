# WBS / Cost Codes — Module 2 Product Contract

## Purpose

WBS / Cost Codes are the internal project control structure used to organize planning, cost allocation and reporting. They are not the contractual BOQ and they are not accounting ledger accounts.

Module 2 is complete when an authorized project user can build and safely maintain a real hierarchy without manual database edits, and downstream project records can retain stable references to that structure.

## Core rules

- WBS belongs to exactly one project and one company.
- Code is a stable project identifier and is unique within the project.
- Code is normalized to uppercase on creation and is not editable later.
- Name and description remain maintainable business labels.
- A code may be a `group`, `trade`, `work_package`, or `cost_code`.
- Hierarchy may be as shallow or deep as the contractor needs; the product does not hardcode one mandatory construction hierarchy.
- A parent must belong to the same project/company.
- Cycles are never allowed.
- New children may only be created under an active parent hierarchy.
- Historical records are never deleted merely because a WBS code is retired.

## Lifecycle

WBS lifecycle is intentionally simple:

`Active → Inactive → Active`

Inactive means the code is retired for new use. Existing project records may continue to reference it for historical reporting.

A parent cannot be made inactive while active descendants remain below it. This keeps the live hierarchy internally consistent and makes retirement an explicit bottom-up operation.

Reactivation requires the full parent chain to be active.

## Historical structure safety

Re-parenting or changing the WBS type can change historical rollups and management reporting. Therefore:

- name and description may continue to change through normal revision control;
- active/inactive lifecycle remains available;
- parent/type changes are allowed only while the WBS subtree has no downstream project usage;
- once any supported downstream record references the code or one of its descendants, the subtree structure is treated as locked.

Usage detection is derived from registered WBS foreign-key consumers rather than a manually maintained editable flag. This allows existing historical references to remain authoritative.

## Permissions

- `commercial.wbs.view` — view project WBS hierarchy and detail.
- `commercial.wbs.manage` — create and revise WBS codes within the authorized project.

Both permissions respect organization and project scope. The UI may hide unavailable actions, but the API remains the authorization boundary.

## API surface

- `GET /api/v1/projects/{project_id}/commercial/wbs`
- `GET /api/v1/projects/{project_id}/commercial/wbs/tree`
- `POST /api/v1/projects/{project_id}/commercial/wbs`
- `GET /api/v1/projects/{project_id}/commercial/wbs/{wbs_id}`
- `PATCH /api/v1/projects/{project_id}/commercial/wbs/{wbs_id}`

There is deliberately no destructive delete endpoint.

## UX surface

- `/commercial/wbs` — project-selectable WBS workspace.
- `/projects/{project_id}/commercial/wbs` — project-specific hierarchy.
- `/projects/{project_id}/commercial/wbs/{wbs_id}` — deep-linked WBS detail.

The workspace shows hierarchy depth, status, child/descendant counts, direct/subtree usage and whether structural edits are locked.

## Shared-platform integration

WBS uses the existing shared capabilities rather than module-specific substitutes:

- project-scoped authorization;
- audit events;
- realtime/outbox events;
- search indexing and deep links;
- optimistic revision control;
- feature/runtime registry.

## Explicit non-goals

Module 2 does not own:

- BOQ quantities/rates or contractual billing;
- estimate/rate-analysis logic;
- budget approval;
- procurement or inventory transactions;
- general-ledger/chart-of-accounts structure;
- statutory tax rules.

Those modules reference WBS where useful but keep their own authoritative business records.
