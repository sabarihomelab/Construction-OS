# Construction OS Release 1 — India Demo Build Baseline

This baseline supersedes the earlier broad/global feature-parity interpretation of Release 1.

Construction OS Release 1 is now an **India-first integrated contractor operating system**. US/UK workflows and foreign product feature catalogs do not define Release 1 scope. Foreign products may still be studied as technical references.

## Release goal

Release 1 is not measured by how many individual modules exist. It is ready when one realistic Indian civil/general contractor project can be demonstrated coherently from project setup and BOQ through site execution, procurement, measurement, RA billing, job cost and management visibility using persisted authoritative data.

The first customer-facing milestone is **one complete India Demo Build**. Internal modules may be completed and validated incrementally, but incomplete engineering checkpoints are not separate customer releases.

## Demo journey acceptance

The integrated demo must be capable of demonstrating, with real persisted relationships:

1. Company and project configuration.
2. Party / client / vendor / subcontractor setup.
3. WBS / Cost Code hierarchy.
4. BOQ creation or controlled Excel import.
5. Estimate / Rate Analysis.
6. Budget baseline and controlled revisions.
7. Worker/crew setup and project assignment.
8. Fast attendance capture, including supervisor-driven bulk attendance.
9. Structured work quantity / progress capture.
10. DPR generated from authoritative attendance/work/material/equipment data where possible.
11. Material requirement / indent.
12. Approval through the shared Workflow engine.
13. RFQ to multiple vendors.
14. Vendor quotations and auditable comparison.
15. Purchase Order with revision/amendment history.
16. Delivery Challan / GRN and quantity/quality acceptance.
17. Site/store inventory derived from transaction history.
18. Material issue/consumption/wastage linked to project control structures where applicable.
19. Equipment assignment/usage and maintenance basics.
20. Practical quality/safety/punch workflow.
21. Subcontract / Work Order.
22. Measurement and certification with separate executed/measured/submitted/certified/billed quantities.
23. Subcontractor cumulative RA Billing with configurable deductions/additions.
24. Basic planning/scheduling/lookahead and DPR progress linkage.
25. Job Cost combining labour + materials + equipment + subcontract + other direct costs.
26. Client contract / measurement / RA Billing / certification / receivable tracking.
27. Versioned India tax/withholding/invoice metadata foundation without hardcoded current statutory rates.
28. Excel/CSV accounting export and Tally integration surface.
29. Project management dashboard with drilldown to originating transactions.
30. Useful PDF/Excel/CSV reports.
31. Closeout basics.
32. Mobile field workflow usable by a supervisor/site engineer.
33. Critical field flows tolerate weak/offline connectivity.

## India-first domain rules

### WBS and BOQ are different

WBS/Cost Codes are the internal project cost/control structure. BOQ is the contractual quantity/rate/billing structure. A BOQ item may map to multiple internal cost components.

### Authoritative quantities and money

Use Decimal/Numeric types. Do not store authoritative quantities only inside descriptive text. Unit conversions must be controlled and incompatible units are never silently converted. INR is the new-company default currency, while currency remains an explicit attribute.

### Worker is not User

A labourer must exist without owning an application account. Workforce supports direct employee, direct labour, contract labour, subcontractor labour, vendor crew and staff concepts. Release 1 prioritizes supervisor-driven fast/bulk attendance over requiring every worker to use a smartphone.

### Party is shared

Client, vendor, supplier, subcontractor, contractor, consultant and service-provider roles should reuse a Party/Business Partner foundation rather than creating unrelated duplicate masters.

### Procurement is core

Canonical Release 1 path:

`Indent → Approval → RFQ → Vendor Quotes → Comparison → Vendor Selection → PO → Delivery/Challan → GRN → Stock → Invoice/accounting reconciliation`

Vendor selection and PO revisions are auditable. Accepted historical commercial values are never overwritten silently.

### Inventory is transactional

Current stock is derived from traceable transactions such as opening balance, GRN receipt, issue, consumption, transfer, return, rejection, wastage, damage and controlled adjustment. Do not use a manually edited balance as the source of truth.

### Measurement is reusable

Measurement/certification is a shared business engine, not logic hidden only inside RA billing. Preserve executed, measured, submitted, certified, billed and paid quantity states separately.

### RA billing is cumulative

Subcontractor and client RA billing preserve previous/current/cumulative quantity and amount. Retention, advance recovery, material recovery, penalty, withholding, tax, debit and other adjustments are configurable/effective-dated; current percentages are not hardcoded into permanent domain logic.

### Accounting strategy

Construction OS Release 1 does **not** attempt to replace a full Indian accounting system. Construction OS owns operational/construction-commercial truth. Accounting remains adapter-driven.

Initial integration priority: controlled Excel/CSV, then TallyPrime. Tally-specific implementation must remain inside an integration adapter rather than business-domain code.

### India compliance

GST/TDS/withholding/e-invoice architecture is jurisdiction-aware, versioned and effective-dated. Historical approved/certified/posted records retain the rule version used at transaction time. Full GST-return filing and full payroll statutory processing are outside the first integrated demo unless later proven necessary.

## Existing module handling

Keep existing valid platform and business foundations. Do not rewrite Projects, Documents/Drawings, RFIs/Submittals, Daily Reports, Workforce, Equipment/Materials, Safety/Inspections/Punch or Meetings merely because the market changed.

Refit them progressively:

- DPR references authoritative WBS/BOQ/activity/worker/material/equipment/measurement records.
- Workforce expands for Indian labour and attendance realities.
- Materials evolves into material master + site/store inventory, with Procurement as a connected bounded context.
- Equipment adds usage/cost allocation over time.
- RFI/Submittal depth is lower priority than BOQ/procurement/measurement/RA billing/job cost.
- Meetings remain useful but lower priority than core commercial execution.
- advanced BIM/CAD/GIS/AI is deferred until the integrated India demo unless a dependency requires otherwise.

## Shared platform requirements

Every module reuses the existing shared platform services: Identity, Authorization, Feature Registry, Configuration, Metadata/Custom Fields, Workflow, Files, Jobs/Outbox, Audit, Notifications, Search, Reporting, Governance, Help, Offline Sync, Realtime Events and Data Portability.

Do not create module-specific substitutes for these capabilities.

## Field UX baseline

The supervisor/site-engineer experience should prioritize clear task actions such as Attendance, Update Work, Material Received, Material Used, Request Material, Equipment, Add Photo, Report Issue and Finish DPR.

Use large touch targets, low typing, defaults, carry-forward, recent values, reusable crews/locations and role-aware navigation. Do not expose unnecessary accounting/commercial complexity to field users.

## Offline / low-bandwidth baseline

Prioritize offline-safe behavior for attendance, DPR, work progress, photos, material transactions, equipment, issues, inspections and safe measurements.

The user must see local save/sync state. Queued changes use durable identity/idempotency, retry/backoff and explicit conflict handling. Field data must never disappear silently.

## Excel and WhatsApp

Excel is a first-class adoption/import/export surface with validation, preview, row-level errors, duplicate detection, tenant/project safety and audit.

WhatsApp is not the system of record. Future WhatsApp integration may deliver DPRs, approval links, reports, reminders and vendor/subcontractor notifications, but authoritative decisions and records must be persisted/audited in Construction OS.

## AI baseline

AI is optional and evidence-based. The first in-app Assistant role is product help, configuration explanation, release/upgrade guidance and retrieval over permitted knowledge.

Future project insights may explain over-budget items, excess material consumption, productivity, unbilled work, pending certifications, stock shortages or delayed activities, but answers must trace to authoritative records.

AI is never authoritative for measurement, billing, tax, withholding, payment, budget, certification or approval decisions. AI also cannot silently execute installer migrations or rollback operations.

## Definition of Done

A capability is not complete merely because code exists. Where applicable it requires persistence, validation/calculation, state handling, tenant/project isolation, authorization, configuration, audit, workflow, notifications/events, files, search, reporting, offline behavior, import/export, concurrency/error handling, indexes, tests, documentation, responsive UX, clean and upgrade migrations and green CI.

## Final Release 1 test

A salesperson/developer must be able to run the India demo without manual database edits, fake UI-only data, broken skipped stages, code changes during the demo, unexplained errors, dead controls, missing permissions or inconsistent totals.

The final question is:

> Can one real Indian contractor run one real project through Construction OS from BOQ and site execution through procurement, measurement, RA billing, cost and management visibility?
