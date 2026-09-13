# India-First Current Repository Refit Assessment

This document is the Phase 0 checkpoint for moving Construction OS from a broad construction platform direction to an **India-first integrated contractor operating system**.

## Classification rule

Every existing capability is classified as `KEEP`, `MODIFY`, `DEPRIORITIZE`, `REMOVE`, or `NEW INDIA REQUIREMENT`. Generic platform capability is not destroyed merely because Release 1 market focus changed.

## Shared platform

| Capability | Classification | India-first action |
|---|---|---|
| Organization / tenant isolation | KEEP | Retain as defense-in-depth even when production deployments are dedicated per customer. |
| Project scope | KEEP | Becomes the main operational boundary for sites/projects. |
| Identity / Sessions / Authentication | KEEP | Continue provider abstraction and strong production authentication. |
| Authorization / Roles | KEEP | Add India personas/presets later; backend remains authoritative. |
| Feature Registry | KEEP | Installer availability → company enablement → role/project permission remains the visibility chain. |
| Configuration / Metadata | KEEP | Use for contractor profiles, fields, terminology, workflows and effective-dated commercial rules. |
| Workflow / Approvals | KEEP | Reuse for indent, PO, measurement, RA bill, certification and configuration approvals. |
| Audit / History | KEEP | Required for commercial, approval and configuration traceability. |
| Files / Media | KEEP | Reuse for challans, GRNs, bills, drawings, photos, work orders and certificates. |
| Notifications | KEEP | Keep actionable; future WhatsApp is a channel, not a second business record. |
| Search | KEEP | Expand to Party, BOQ, PO, GRN, measurement, RA bill and material. |
| Realtime / Outbox | KEEP | Continue targeted invalidation and post-commit event rules. |
| Offline / Sync | KEEP | Increase priority for attendance, DPR, material, equipment and measurements. |
| Background Jobs | KEEP | Reuse for imports, exports, reports, document processing and integrations. |
| Reporting | KEEP | Refocus projections on Indian contractor management information. |
| Integration / Mapping | KEEP | Prioritize Excel/CSV and Tally adapters. |
| Setup / Templates | KEEP | Add Civil Contractor and India default presets. |
| Retention / Governance | KEEP | Apply especially to commercial and compliance records. |
| Help / Knowledge | KEEP | Extend into evidence-based Construction OS Assistant/RAG. |
| Health / Diagnostics | KEEP | Include integration, backup, worker and database readiness. |

## Existing business modules

| Capability | Classification | India-first action |
|---|---|---|
| Projects | KEEP | Add WBS/cost structure, Party and commercial relationships progressively. |
| Documents / Specifications | KEEP | Connect to PO/GRN/work order/measurement/bill/certification over time. |
| Drawings | KEEP / DEPRIORITIZE ADVANCED | Preserve core revision/markup capability; advanced BIM/CAD intelligence is not a pre-demo priority. |
| RFIs | KEEP / DEPRIORITIZE DEPTH | Preserve backend; do not let foreign-style RFI depth displace BOQ/procurement/measurement work. |
| Submittals | KEEP / DEPRIORITIZE DEPTH | Preserve backend; integrate only where Indian project workflow requires it. |
| Daily Reports / Field | MODIFY | Evolve into DPR aggregation over attendance, quantity, materials, equipment, issues and photos. |
| Workforce / Time | MODIFY | Add worker category, employer/contractor, wage basis, shifts, fast supervisor bulk attendance and labour cost allocation. |
| Equipment | MODIFY | Add operating/idle hours, fuel, breakdown, hire rate/cost and WBS/activity allocation. |
| Materials | MODIFY | Split operational material master from proper inventory/site-store transaction history; procurement becomes a connected bounded context. |
| Safety / Inspections / Punch | KEEP | Keep practical basics; integrate site workflow and closure evidence. |
| Meetings | KEEP / DEPRIORITIZE | Useful shared coordination capability but lower priority than commercial execution. |
| Full accounting replacement | REMOVE FROM RELEASE 1 PRIORITY | Construction OS owns construction-commercial truth; accounting remains adapter-driven. |

## New India requirements

The current repository does not yet provide the following complete India-first domain contracts and they are now the major development priority:

1. Party / Business Partner directory
2. WBS / Cost Code hierarchy
3. BOQ hierarchy/items/revisions/mappings
4. Estimate / Rate Analysis
5. Budget baseline and approved revisions
6. Contract labour + bulk attendance
7. Structured executed work quantity
8. Material Master + Site/Store + inventory transaction ledger
9. Procurement: Indent → Approval → RFQ → Quote → Comparison → PO → GRN
10. Subcontract / Work Order
11. Reusable Measurement / Certification engine
12. Subcontractor RA Billing
13. Client Contract / Client RA Billing / Certification
14. Job Cost / Commercial Control
15. India Tax / Withholding / Invoice metadata foundation
16. Controlled Excel/CSV import/export surfaces
17. Tally/accounting adapter
18. India management dashboards
19. Integrated India demo data
20. India-first responsive/offline UX hardening

## Priority changes from previous roadmap

The previous roadmap emphasized broad global parity including deep drawings, RFIs/Submittals, bidding/change-management and full accounting coverage. Those capabilities are not necessarily removed, but they no longer drive Release 1.

New critical path:

`Party → WBS/Cost Codes → BOQ → Estimate/Budget → Workforce/Attendance → DPR → Inventory/Procurement → Equipment → Subcontract → Measurement → RA Billing → Job Cost → Client Billing → India commercial rules → Tally/Excel → Dashboard/Reports`

## Data relationship refit

Existing free-text relationships should be reduced progressively when authoritative master data exists. Future field records should reference canonical Worker/Crew, Party, WBS, Cost Code, BOQ Item, Material, Equipment, PO/GRN, Schedule Activity, Project Location and Measurement objects where applicable.

Do not perform destructive conversions without explicit mapping. Existing free text can remain as historical notes/descriptions while new structured relationships are added.

## Dedicated deployment model

Commercial deployment is planned as one customer environment per installation, cloud or on-premises. Existing `organization_id` isolation remains valuable and should not be removed.

Deployment composition remains independent from business configuration:

`Infrastructure profile → runtime modules/workers → company configuration → project configuration → user experience`

## Immediate engineering gate

Before adding major new business modules:

- India defaults must replace US defaults for new company setup.
- README/product requirements must explicitly state India-first priority.
- old foreign-market parity language must not define Release 1.
- the in-app AI assistant must have a safe evidence/authority boundary.
- current generic foundations remain reusable.

After this refit is green, resume development from Party / Business Directory rather than the previous global module sequence.
