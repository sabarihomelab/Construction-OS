# Construction OS — India-First Product Contract

## Product direction

Construction OS is an **India-first construction operating platform**. Release 1 is optimized for small and mid-sized Indian civil/general contractors managing multiple active sites, while remaining usable for builders, MEP contractors and specialty subcontractors.

Foreign construction products may be studied only as technical/product references. They do **not** define Construction OS terminology, accounting, compliance, workflow or Release 1 priorities.

Primary product inputs are Indian contractor workflows: BOQ, measurement, RA billing, subcontract work, labour/contract labour, material planning and procurement, site inventory, GST/TDS-aware commercial records, Excel-heavy processes, Tally/accounting integration, WhatsApp-heavy communication and low-bandwidth/mobile site work.

The customer-facing objective is **one complete integrated India demo build**, not a sequence of incomplete customer releases.

## Product principle

> Complex underneath. Simple on top.

Information is entered once and reused through authoritative relationships. A normal field user should not need to understand commercial or platform internals.

Target connected flow:

`Attendance + Work Quantity + Material Consumption + Equipment Usage → DPR → WBS/BOQ/Activity → Actual Progress + Actual Cost → Measurement → RA Billing → Management Visibility`

Do not create duplicate independent truths for the same real-world event.

## India demo journey

The first meaningful customer demo should support a realistic persisted journey:

`Company → Project → Party → WBS/Cost Codes → BOQ → Estimate/Rate Analysis → Budget → Workforce/Crews → Attendance → DPR/Work Quantity → Material Requirement → Approval → RFQ → Quotes → Comparison → PO → Delivery/GRN → Site Inventory → Issue/Consumption → Equipment Usage → Measurement → Subcontract Work Order → Subcontract Measurement → Subcontractor RA Bill → Certification/Deductions → Client Measurement → Client RA Bill → Receivable → Job Cost → Planned vs Actual → Dashboard/Reports → Accounting Export/Tally Bridge → Closeout basics`

## Existing capability handling

### Keep and reuse

Keep the existing platform foundations: Organization/tenant isolation, Projects, Identity, Authentication, Sessions, Authorization, Roles/Permissions, Feature Registry, Configuration, Metadata/Custom Fields, Workflow/Approvals, Audit/History, Files/Media, Notifications, Search, Realtime/Outbox, Offline/Sync, Background Jobs, Reporting, Integrations/Mapping, Setup/Templates, Retention/Governance, Help and Health/Diagnostics.

Keep existing business foundations for Projects, Documents/Drawings, RFIs/Submittals, Daily Reports/Field, Workforce, Safety/Inspections/Punch, Equipment/Materials and Meetings. Modify priorities and domain relationships rather than rewriting valid generic foundations.

### Modify for India

- Daily Reports become structured DPR aggregation over authoritative attendance, quantities, materials, equipment and issues.
- Workforce expands for direct labour, contract labour, subcontractor labour, vendor crews, supervisors, shifts and fast bulk attendance.
- Materials expands into material master + site/store inventory + traceable movements.
- Procurement becomes a core Release 1 flow: Indent → Approval → RFQ → Quote → Comparison → PO → GRN.
- Financial direction becomes construction commercial control/job cost plus accounting integration, not a full General Ledger replacement.
- Scheduling remains practical: activities, hierarchy, dependencies, baseline/lookahead, progress and delay linkage rather than a Primavera/MS Project clone.

### Lower priority before the integrated demo

Deep Procore-style RFI/Submittal behavior, advanced BIM/CAD/GIS, advanced drawing intelligence, full statutory payroll, full GST return filing, property sales/CRM/facility management and advanced autonomous AI.

## New India-first domain backbone

The following business foundations drive the next development sequence:

1. Party / Business Directory
2. WBS / Cost Codes
3. BOQ
4. Estimate / Rate Analysis / Budget Baseline
5. Workforce / Contract Labour / Attendance
6. DPR integration
7. Material Master / Inventory / Site Store
8. Procurement
9. Equipment
10. Quality / Safety / Punch integration
11. Subcontract / Work Order
12. Measurement / Certification Engine
13. Subcontractor RA Billing
14. Basic Planning / Scheduling / Lookahead
15. Job Cost / Commercial Control
16. Client Contract / Client RA Billing / Certification
17. India Tax / Withholding / Invoice foundation
18. Accounting Export / Tally integration
19. Correspondence / Meetings / Approvals
20. Reporting / Dashboards / Portfolio
21. Closeout
22. Integrated India demo data
23. Release 1 web/mobile UX integration
24. Offline/low-bandwidth hardening
25. Security/performance/reliability/demo readiness

## Party model

Use one reusable Party / Business Partner foundation for client, vendor, supplier, subcontractor, contractor, consultant and service provider roles. Avoid independent duplicate vendor/client/subcontractor masters.

India-specific identifiers must be jurisdiction-aware and sensitive identifiers require restricted permissions.

## WBS and BOQ

WBS/Cost Codes are the internal project control/cost backbone. BOQ is the contractual quantity/rate/billing backbone. They are related but **not the same object**.

Authoritative quantities and money use Decimal/Numeric. Units are controlled and incompatible units are never silently converted.

## India commercial foundation

Construction OS Release 1 is **not** a replacement for Tally or a full accounting suite. Construction OS owns operational and construction-commercial truth; accounting software may remain the accounting book of record.

Integration pattern:

`Construction OS domain → Accounting integration contract → adapter → TallyPrime / CSV / other accounting system`

Initial adoption priority is controlled Excel/CSV import/export followed by Tally integration.

GST/TDS/e-invoice concepts must be versioned and effective-dated. Do not hardcode current tax rates, thresholds or section numbers into permanent domain columns or logic. Historical approved/certified transactions retain the exact rule version applied at the time.

## India localization

New-company India preset:

- country: `IN`
- locale: `en-IN`
- timezone: `Asia/Kolkata`
- currency: `INR`
- unit system: metric
- Indian financial-year capable
- Indian address capable

Future language support may include English, Hindi, Tamil, Telugu, Kannada, Malayalam and Marathi. User-facing translated text must not be hardcoded inside business-domain logic.

## Field UX

Typical supervisor landing experience should favor task actions such as Mark Attendance, Update Work, Material Received, Material Used, Request Material, Equipment, Add Photo, Report Issue and Finish DPR.

Use large touch targets, minimal typing, defaults, carry-forward, recent values, reusable crews/locations and selectors. Commercial/accounting complexity must not leak into simple field workflows.

## Offline / low-bandwidth

Offline is a baseline for field-critical workflows: attendance, DPR, work progress, photos, material transactions, equipment, issues, inspections and safe measurements.

Local save must be immediate and visible. Mutations queue durably, retry with backoff, synchronize when connectivity returns and surface conflicts explicitly. Never silently lose field data.

## Historical safety

Continue using change classes: `PRESENTATION`, `METADATA`, `BUSINESS_RULE`, `WORKFLOW`, `FINANCIAL`, `SECURITY`.

Historically used configuration is retired/versioned rather than destructively deleted where reproducibility matters. Approved measurements, certified bills, PO revisions, work orders, budget versions and posted financial records remain reproducible.

## AI direction

AI comes after authoritative structured data. Construction OS Assistant may use retrieval-augmented generation for product help, release notes, setup/configuration explanation, upgrade readiness and future project insights.

AI answers must expose evidence. AI is never authoritative for measurement, billing, tax, withholding, payment, budget, certification or approvals. Upgrade/rollback actions remain deterministic installer operations requiring explicit operator control.

## Final development test

Do not optimize for the number of coded modules. Optimize for this question:

> Can one real Indian contractor run one real project through Construction OS from BOQ and site execution through procurement, measurement, RA billing, cost and management visibility?
