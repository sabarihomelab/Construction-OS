# Bill of Quantities — Release 1 Contract

## Purpose

The BOQ is the project's contractual or controlled quantity/rate baseline. It is deliberately separate from WBS / Cost Codes:

- WBS / Cost Codes organize internal planning, cost allocation and reporting.
- BOQ lines represent measurable commercial quantities and rates.
- A BOQ line may map to one WBS code, but the BOQ does not become the WBS hierarchy.

## Release 1 lifecycle

`Draft → Approved`

A draft may also move to `Cancelled` when it has not become a downstream dependency.

Approved BOQs are immutable. Approval creates an immutable snapshot in `project_boq_revisions` containing the BOQ header, line quantities/rates, WBS code evidence, total value and approval metadata.

Release 1 does not silently reopen an approved BOQ. Contract amendments that need successor-line lineage are a separate controlled extension; they must not mutate an already-used approved baseline.

## BOQ identity

- BOQ code is unique within a project and is normalized to uppercase.
- Code is a stable identifier and cannot be edited after creation.
- Name and description may change while draft.
- Currency is explicit. New India-first BOQs default to INR.
- Currency cannot change after lines exist because doing so would change the meaning of recorded rates.

## BOQ lines

Every line stores authoritative structured values:

- line number
- item code
- description
- unit
- quantity
- rate
- calculated amount
- optional WBS mapping
- optional HSN/SAC metadata
- optional notes

Money and quantity remain Numeric/Decimal values. Authoritative values are not stored only in descriptive text.

Line number and item code are unique within a BOQ.

## WBS mapping

WBS mapping is optional because the contractual BOQ and internal control structure are different concepts. When a mapping is supplied:

- the WBS must belong to the same organization and project;
- it must be active when the BOQ line is created or changed;
- all mapped WBS codes must still be active when the BOQ is approved.

Historical approved BOQ snapshots retain the WBS code used at approval time.

## Draft editing and downstream safety

Draft lines can be created, edited and deleted.

If a BOQ line has already become a downstream dependency, the line cannot be edited or deleted through the BOQ module. The dependent record must be corrected or unlinked through its own governed workflow first. This prevents silent changes to estimating, procurement, measurement, subcontract or other project records.

The BOQ itself is never destructively deleted through the customer API.

## Approval

Approval requires:

1. `commercial.boq.approve` permission in the project.
2. The current BOQ revision to match the user's expected revision.
3. At least one BOQ line.
4. Every mapped WBS code to remain active.

Approval:

- records the approving membership and timestamp;
- calculates the current BOQ total;
- creates an immutable versioned snapshot;
- changes status to Approved;
- writes a critical audit event;
- publishes realtime/search updates.

After approval, header and line mutation routes reject changes.

## Controlled CSV / Excel-compatible import

Release 1 provides a controlled CSV path that can be produced from Excel without adding a spreadsheet-processing runtime dependency.

Required columns:

- `line_number`
- `item_code`
- `description`
- `unit_code`
- `quantity`
- `rate`

Optional columns:

- `wbs_code`
- `hsn_sac`
- `notes`

Import is intentionally two-step:

`CSV → Preview / validation → Apply`

Preview validates required columns, numeric precision, duplicates, existing BOQ collisions, field lengths and WBS status. It returns row-level errors and the valid-row total.

Apply reruns validation while locking the draft BOQ, checks the expected BOQ revision, rejects the whole import if any row is invalid and inserts all accepted rows in one transaction. Partial imports are not silently committed.

The first implementation supports up to 5,000 data rows and 2 MB of CSV text per request.

## Export and portability

Users can export:

- the current BOQ as CSV;
- each approved immutable snapshot as CSV;
- a BOQ import template.

The approved snapshot export uses the values captured at approval rather than rebuilding history from mutable masters.

## Search, authorization and audit

BOQ remains project scoped.

- `commercial.boq.view` controls read access.
- `commercial.boq.manage` controls draft create/edit/import/cancel actions.
- `commercial.boq.approve` controls baseline approval.

Mutations use CSRF protection, project authorization and server-derived organization identity. Client payloads never choose the tenant.

Create/update/delete/import/approve/cancel actions are audited. BOQ changes publish realtime/outbox events and refresh the search projection.

## Customer workspace

The BOQ workspace supports:

- project selection;
- draft/approved/cancelled filtering;
- BOQ creation;
- draft header editing;
- manual line entry;
- line edit/delete;
- WBS mapping;
- controlled CSV preview/apply;
- current and approved-version CSV export;
- approval and cancellation;
- approved revision history.

## Explicit non-goals for Module 3

Module 3 does not implement:

- measurement/certification logic;
- RA billing;
- rate analysis or budget creation;
- full GST calculation;
- contract amendment successor-line lineage;
- statutory accounting;
- Tally-specific logic.

Those capabilities reference the BOQ but remain in their own bounded contexts.
