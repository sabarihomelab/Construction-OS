# Construction OS — India-First Product Contract

## Product direction

Construction OS is an **India-first construction operating platform**. Release 1 is optimized for small and mid-sized Indian civil/general contractors managing multiple active sites, while remaining usable for builders, MEP contractors and specialty subcontractors.

Foreign construction products may be studied only as technical/product references. They do **not** define Construction OS terminology, accounting, compliance, workflow or Release 1 priorities.

Primary product inputs are Indian contractor workflows: client enquiry and quotation, BOQ, estimation/rate analysis, measurement, RA billing, subcontract work, labour/contract labour, material planning and procurement, site inventory, GST/TDS-aware commercial records, Excel-heavy processes, Tally/accounting integration, WhatsApp-heavy communication and low-bandwidth/mobile site work.

Release 1 is optimized for small and mid-sized contractors, but canonical business objects must remain suitable for larger contractors. Large-company depth is added through configuration and governance rather than a separate enterprise data model.

The customer-facing objective is **one complete integrated India demo build**, not a sequence of incomplete customer releases.

## Product principle

> Complex underneath. Simple on top.

Information is entered once and reused through authoritative relationships. A normal field user should not need to understand commercial or platform internals.

Target connected flow:

`Client Enquiry → Preliminary/Detailed Estimate → Quotation → Client Acceptance → Award → BOQ/Budget Baseline → Attendance + Work Quantity + Material Consumption + Equipment Usage → DPR → WBS/BOQ/Activity → Commitments + Actual Cost + Progress → Measurement → RA Billing/Client Billing → Receipts → CVR/Profitability → Accounting Integration`

Do not create duplicate independent truths for the same real-world event.

## India demo journey

The first meaningful customer demo should support a realistic persisted journey:

`Company → Client Enquiry / Pre-Construction Job → Drawings / Requirements → Parametric or Detailed Estimate → Rate Analysis / Rate Library Selection → Versioned Quotation → PDF Issue → Client Acceptance → Controlled Award / Project Activation → Party → WBS/Cost Codes → Contractual BOQ → Approved Cost Budget → Workforce/Crews → Attendance → DPR/Work Quantity → Material Requirement → Approval → RFQ or configured direct purchase → Quotes/Comparison where required → PO → Delivery/GRN → Site Inventory → Issue/Consumption → Equipment Usage → Measurement → Subcontract Work Order → Subcontract Measurement → Subcontractor RA Bill → Certification/Deductions → Client Measurement / Stage Billing → Client RA Bill / Invoice → Receipt → Job Cost → Commitment/Actual/Forecast/CVR → Dashboard/Reports → Accounting Export/Tally Bridge → Closeout basics`

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

## Pre-construction, quotation and award

Construction OS starts before a project is won.

A client enquiry or pre-construction job may collect client/site details, drawings, built-up area, floors, specification tier, structural/finish/MEP selections, contract type and other estimating parameters without treating the opportunity as an active execution project.

Supported estimating paths:

```text
Fast ballpark / parametric estimate
        ↓
Detailed estimate / rate analysis
        ↓
Versioned customer quotation
        ↓
Issue / negotiate / revise
        ↓
Client acceptance
        ↓
Controlled award / conversion
        ↓
Contractual BOQ + approved internal budget + active project controls
```

The per-square-foot figure is a derived commercial presentation metric, not the authoritative calculation engine. Detailed cost remains component-based: material, labour, equipment, subcontract, overhead and other governed cost components, with configured wastage/overhead/profit.

Quotation revisions are immutable historical commercial evidence. A later revision never overwrites an already issued quotation. Acceptance records the accepted revision, date, commercial amount and evidence/actor as applicable.

Project award is a controlled boundary. It creates or activates downstream project-control baselines from the accepted commercial scope without silently changing the accepted quotation.

See `PRECONSTRUCTION-QUOTATION.md`.

## Rate and supplier intelligence

Material price intelligence is separate from physical inventory.

The platform should maintain a governed Rate Library/Price History capable of recording company historical purchases, supplier quotations, manual market references and approved external feeds by material/specification, unit, location, supplier/source and effective date.

New prices may be proposed during estimating, but an approved/issued estimate or quotation snapshots the selected rate and source context. Later market updates never recalculate historical quotations, approved estimates or budgets.

The company's own PO/GRN/vendor-bill history should become a primary trusted source of future estimating references. Web scraping or AI extraction may enrich the rate library but must not become the sole authoritative rate source.

## Enterprise-down operating model

Do not create separate small, mid-market and enterprise business engines.

The same canonical transactions are exposed with different workflow depth:

- Small contractor: direct/simple material request, owner/PM approval, PO or controlled direct purchase, GRN, simple site inventory, attendance, DPR, expenses, client receipts and profitability.
- Mid-market contractor: requisition, configurable approval, RFQ/quote comparison, PO, multi-store inventory, formal subcontracts/measurements/RA billing and stronger budget control.
- Large contractor: procurement packages, central/regional purchasing, vendor prequalification, technical/commercial evaluations, value-based approval matrices, framework/rate contracts, warehouses/transfers, contract/change/claim administration, accruals, ETC/EAC forecasting and formal CVR.

Configuration may shorten a workflow, but it must not create a second definition of PO, GRN, BOQ, inventory, cost or subcontract data.

## Party model

Use one reusable Party / Business Partner foundation for client, vendor, supplier, subcontractor, contractor, consultant and service provider roles. Avoid independent duplicate vendor/client/subcontractor masters.

India-specific identifiers must be jurisdiction-aware and sensitive identifiers require restricted permissions.

## WBS and BOQ

WBS/Cost Codes are the internal project control/cost backbone. BOQ is the contractual quantity/rate/billing backbone. They are related but **not the same object**.

BOQ is not a mandatory parent for every project transaction. Where a cost, commitment, inventory movement or measurement genuinely represents BOQ scope, retain explicit BOQ lineage. Legitimate non-BOQ costs such as site establishment, temporary works, security, local transport or other indirect/site costs remain governed through WBS/Cost Head/project-cost structures rather than being forced onto artificial BOQ lines.

Authoritative quantities and money use Decimal/Numeric. Units are controlled and incompatible units are never silently converted.

## India commercial foundation

Construction OS Release 1 is **not** a replacement for Tally or a full accounting suite. Construction OS owns operational and construction-commercial truth; accounting software may remain the accounting book of record.

Integration pattern:

`Construction OS domain → Accounting integration contract → adapter → TallyPrime / CSV / other accounting system`

Initial adoption priority is controlled Excel/CSV import/export followed by Tally integration. Tally integration must remain adapter-based so transport/protocol details can evolve without changing Construction OS business objects.

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

> Can one real Indian contractor take a customer from enquiry and quotation through award, execution, procurement, measurement, billing, cost, profitability and accounting handoff without creating duplicate truths or leaving the system for core project control?
