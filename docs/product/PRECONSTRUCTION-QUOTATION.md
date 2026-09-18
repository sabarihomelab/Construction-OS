# Pre-Construction / Quotation / Award

## Purpose

Construction OS begins before site execution. This contract governs the customer-enquiry-to-award stage for Indian contractors, especially small and mid-sized builders/general contractors that currently prepare quotations in spreadsheets or disconnected estimating tools.

The module must support fast preliminary pricing without weakening the governed Estimate/Rate Analysis, BOQ, Budget and Project Cost foundations used after award.

## Core principles

1. A client enquiry is not yet an active construction project.
2. Parametric estimates are working proposals, not approved financial truth.
3. Detailed component-based estimating is preferred before a formal quotation is issued.
4. The customer quotation is selling/commercial evidence; it is not the internal cost budget.
5. Issued quotation revisions are immutable historical evidence.
6. Client acceptance pins the exact accepted revision.
7. Award/conversion is an explicit controlled transition into project execution.
8. Accepted quotation, contractual BOQ and internal approved budget remain distinct objects.
9. The displayed ₹/sq.ft. value is a derived metric, not the hidden authoritative calculation engine.
10. AI/OCR may assist extraction/classification but never silently approves quantities, rates, quotation values or award.

## Pre-construction journey

```text
Client Enquiry
    ↓
Pre-Construction Job
    ↓
Client / Site / Drawing / Requirement Intake
    ↓
Parametric Estimate (optional)
    ↓
Detailed Estimate / Rate Analysis
    ↓
Rate Library / Supplier Price Selection
    ↓
Quotation Draft
    ↓
Issue Revision
    ↓
Negotiation / Revision
    ↓
Accepted / Rejected / Expired
    ↓
Controlled Award
    ↓
Active Project + Contractual BOQ + Internal Budget
```

## Pre-construction workspace

For Release 1, reuse the existing Project aggregate in `PLANNING` status as the pre-construction workspace. This keeps Estimate, Files, Party assignment, authorization and later BOQ/Budget relationships on the same stable project UUID and avoids creating a duplicate opportunity/project hierarchy.

A planning project is not yet an execution project: field execution, governed award-dependent financial actions and other configured downstream capabilities remain unavailable until award/activation.

A separate CRM-style Opportunity aggregate may be introduced later only if the product needs leads that should exist without any project workspace.

The pre-construction workspace is organization-owned and becomes the same project after award.

Typical attributes:

- enquiry/opportunity number;
- client Party or prospect contact;
- project/site name;
- address/locality/region;
- building/project type;
- built-up area and governed area basis;
- floor count;
- specification tier;
- contract type;
- target start/completion information where known;
- notes/requirements;
- drawing/specification/file references;
- assigned estimator/owner;
- status and revision.

Suggested lifecycle:

`Enquiry → Estimating → Quoted → Negotiation → Accepted / Rejected / Expired → Awarded`

Statuses are business states; deleted/rejected opportunities must not erase already issued quotation history.

## Parametric estimation

Parametric estimation provides a rapid starting point for customers who need an early construction-cost indication.

Configurable inputs may include:

- built-up area;
- floors;
- structural system;
- substructure/superstructure selections;
- masonry;
- flooring/finishes;
- doors/windows;
- electrical/plumbing/HVAC;
- specification tier;
- locality;
- contract type;
- contractor-specific coefficients/templates.

Templates may suggest WBS/work items and quantities using deterministic formulas. Every generated value must expose its input/assumption and remain reviewable before formal quotation.

A simple ballpark may use ₹/sq.ft., but a detailed quotation should derive the final effective ₹/sq.ft. from the governed calculated total and area basis.

## Detailed estimate / rate analysis

Detailed estimates use the existing Estimate/Rate Analysis engine.

Rate build-up categories remain:

- material;
- labour;
- equipment/machinery;
- subcontract;
- overhead;
- other governed cost.

Wastage, overhead and profit remain explicit inputs/rules. Customer selling price and internal cost are preserved separately.

## Rate Library / Price History

Rate intelligence is a separate business capability from Inventory.

A rate observation should support, where applicable:

- material/service master;
- specification/grade/brand;
- unit;
- locality/region;
- supplier/source Party;
- rate;
- tax/freight basis or notes;
- effective/observed date;
- source type;
- source evidence/reference;
- captured timestamp;
- active/expired state.

Preferred sources are the contractor's own governed PO/GRN/vendor-bill history and supplier quotations. Manual/company masters, vendor feeds and approved external references may supplement them.

An estimate/quotation snapshots the selected rate and source context. New rate observations never rewrite issued quotations, approved estimates or budgets.

## Quotation

A quotation is a customer-facing commercial offer.

Typical content:

- contractor/company identity and branding;
- client/site/project summary;
- quotation number and revision;
- issue date and validity;
- built-up area / area basis;
- project/specification summary;
- scope/work-package cost summary;
- optional detailed line items;
- total quoted amount;
- derived ₹/sq.ft.;
- assumptions;
- inclusions;
- exclusions;
- allowances/provisional items;
- payment terms/stages where applicable;
- taxes/commercial notes;
- indicative duration where configured;
- company/contact details.

PDF generation uses persisted quotation revision data, not mutable current masters where historical reproducibility matters.

## Quotation revision lifecycle

Suggested states:

`Draft → Issued → Negotiation → Accepted / Rejected / Expired / Superseded`

Rules:

- draft may be edited by authorized users;
- issue creates an immutable revision snapshot;
- negotiation changes create a new revision rather than altering the previously issued revision;
- acceptance identifies one exact issued revision;
- only one accepted/current award basis may exist for a given pre-construction job unless a governed amendment process explicitly changes it;
- rejection/expiry never deletes historical revisions.

## Award / project conversion

Award is the boundary between sales/pre-construction and governed project execution.

Award should be transactional/idempotent and able to create or establish:

- transition the existing planning Project to the governed awarded/active execution state;
- client Party/project relationship;
- accepted contract/quotation value;
- initial WBS/Cost Codes from approved templates/estimate structure;
- contractual BOQ by controlled conversion/mapping/import;
- approved/draft internal project budget based on configured policy;
- project team/PM assignment;
- baseline commercial references and source lineage.

Do not copy the quotation selling rate into the project cost budget as though it were cost. The budget uses approved internal estimate cost.

Award failure must not leave half-created baselines. Retry must be idempotent.

## Drawings and requirements

Blueprints/drawings may be attached during pre-construction and later promoted/linked into the active project document/drawing domain.

Drawing revisions must retain current/superseded status. A quotation should be able to reference the drawing/specification revision basis used for pricing.

Advanced BIM/CAD quantity takeoff is optional/future functionality; ordinary PDF/image/drawing intake must work without it.

## Variations after award

Post-award customer changes are not quotation rewrites.

Use governed project variation/change control:

```text
Original Contract
+ Approved Variation(s)
= Revised Contract Value
```

Original BOQ/contract/quotation evidence remains reproducible.

## Access and commercial confidentiality

Typical visibility can be configured:

- Owner/Director: quotation selling price, margin, all projects.
- Estimator/QS/Commercial: estimate/rate analysis/quotation according to permissions.
- PM: awarded project budget/commercial data as granted.
- Supervisor: field execution data; no automatic access to contractor profit/margin.

Job titles are not authorization. Existing organization/project roles and atomic permissions remain authoritative.

## Small / mid / large contractor behavior

The pre-construction objects remain the same across company size.

Small contractor:
- owner/estimator prepares quotation;
- simple templates and recent supplier prices;
- owner accepts award;
- compact PDF and project conversion.

Mid-market:
- estimator/QS prepares;
- commercial/PM review;
- quotation approval workflow;
- richer vendor/rate history;
- formal handover to PM.

Large contractor:
- opportunity/tender package;
- estimator/QS/commercial separation;
- multi-level bid review;
- tender clarifications/addenda;
- procurement-package and subcontract strategy;
- controlled tender-to-budget handover.

Enterprise depth is added later without redefining Estimate, Quotation, BOQ or Budget meaning.

## Offline and mobile

Quotation/estimating is primarily office/web oriented. Field-critical execution remains the priority for offline mobile.

Mobile may capture site survey notes/photos/basic pre-construction data, but authoritative quotation issue/acceptance/award should be server-governed.

## Audit

Audit at minimum:

- enquiry/pre-construction creation and status changes;
- estimate/quotation issue;
- quotation revision creation;
- acceptance/rejection/expiry;
- selected rate-source changes for issued commercial evidence;
- award/conversion;
- project/BOQ/budget lineage created from award.

## Reporting

Required views should eventually include:

- enquiries by status;
- quotation pipeline;
- quote value and revision history;
- accepted/rejected/expired quotations;
- win/loss counts without AI inference;
- expected vs awarded value;
- awarded quotation → project traceability;
- quoted vs current forecast margin after execution begins.

## Release 1 implementation impact

Reuse existing foundations rather than rewriting them:

- `Project` in `PLANNING` status is the pre-construction workspace.
- existing Party/ProjectParty relationships represent the prospective/accepted client.
- existing Estimate/Rate Analysis remains the detailed calculation engine.
- existing Files/Documents foundations store drawings, specifications and quotation evidence.
- existing Workflow/Audit/Events/Jobs/Reporting services govern approval, history, PDF generation and notifications.
- existing BOQ and Budget engines remain post-award governed baselines.

Additive domain capability required:

- quotation header and immutable quotation revision/snapshot records;
- quotation issue/accept/reject/expire/supersede lifecycle;
- pre-construction parameter/template data for deterministic parametric estimates;
- organization-owned Rate Library / Price Observation records with source/effective-date history;
- selected-rate snapshot lineage on issued quotation/approved estimate evidence;
- controlled award/conversion service that validates accepted revision and creates/maps BOQ/Budget baselines atomically;
- quotation PDF/export provider;
- permissions, audit, search, reporting and tests for the above.

Do not change existing Project/BOQ/Estimate IDs merely to add pre-construction. Prefer additive migrations and services.

## Implementation boundary

Reuse existing shared services for authorization, workflow, audit, files, jobs, configuration, search, reporting, events and templates.

Do not create a separate pre-construction identity, file, approval, audit or reporting framework.

New backend/domain implementation should be additive around the existing Estimate, BOQ, Project and Financial foundations and must preserve current historical-safety rules.
