# Construction OS Full Product Release Requirements Baseline

This document converts recurring construction-user feedback into an explicit Construction OS release baseline. It supplements module contracts and architecture standards; it does not replace them.

## Release interpretation

A requirement may be architecturally planned without being implemented. Construction OS must not claim a capability is released until it satisfies the module Definition of Done: real persistence, validation, authorization, tenant isolation, error handling, audit where relevant, responsive/mobile behavior, offline behavior where required, search/filtering, tests, documentation and real dashboard/report integration.

## Coverage matrix

| # | Requirement | Current coverage | Release action |
|---|---|---|---|
| 1 | Field-first UX | Partial | Add field-task UX standards: minimal taps, role/task-specific layouts, touch targets, carry-forward and low-training workflows. |
| 2 | Offline-first mobile | Partial | Add dedicated Offline Sync & Device State platform module with local encrypted storage, durable queue, retry, conflict handling, acknowledgement and visible sync status. |
| 3 | Performance is a feature | Partial | Add measurable performance budgets for startup/login, project switching, drawings, search, scrolling, saves, sync and dashboards. |
| 4 | Global search | Partial | Expand Search & Indexing contract to all supported business objects, module search, filters and preservation of navigation/search state. |
| 5 | Drawing engine | Missing explicit module | Add Drawings module plus drawing/geometry architecture for sets, sheets, revisions, overlays, markups, measurements, pins, calibration, offline packages and mobile rendering. |
| 6 | Estimating engine | Missing explicit module | Add Estimating and Takeoff modules with structured spreadsheet-like calculations, formulas, assemblies, resources, versions, comparison, cost codes and first-class Excel import/export. |
| 7 | Scope intelligence | Partial/future AI | Add evidence-based estimating intelligence contract for drawing/spec comparison, scope gaps, bid exclusions and revision differences. AI suggests; human confirms. |
| 8 | Bidder/external collaborator experience | Partial | Extend identity/access with temporary scoped collaboration and add Bid Management/External Collaboration module. Avoid unnecessary full user seats. |
| 9 | RFIs | Planned, not contracted | Add full RFI module contract including drawing/spec/location/schedule/cost links, workflow, due dates, escalation, history and ball-in-court. |
| 10 | Submittals | Planned, not contracted | Add Package -> Items -> Revisions model, workflow/attachments and specification/drawing/procurement/schedule/lead-time links. |
| 11 | Notification engine | Partial | Existing platform Notification module must add priority taxonomy, reason-for-notification, preferences, channels, quiet hours, digests, escalation and subscriptions. |
| 12 | Daily report / field data | Partial | Expand Field module contract for crews, carry-forward, voice, photos, weather, manpower, equipment, deliveries, production, delays, visitors, safety, T&M and downstream reuse. |
| 13 | Time & workforce | Partial | Expand Workforce/Time contracts for internal/subcontract labor, crews, time types, cost codes, location, equipment, production, approvals and offline entry. |
| 14 | Scheduling | Missing detailed contract | Add Scheduling module for activities, dependencies, milestones, critical path, baselines, look-aheads, constraints, calendars, actuals, delays and procurement/submittal integration. |
| 15 | Change management | Missing detailed contract | Add connected Potential Issue -> Change Event -> Cost/Quantity -> RFQ -> Quote -> Review -> Owner Change -> Commitment -> Budget/Job Cost -> Billing chain. |
| 16 | Native construction financials | Partial/high-level | Add finance domain contracts for COA, cost codes, jobs, budgets, commitments, POs, AP, AR, progress billing, retainage, change orders, payroll, job cost, GL, cash, equipment costing and reporting. Jurisdiction-specific tax/payroll remains configuration-dependent. |
| 17 | Reporting | Partial | Expand Reporting/Analytics into configurable grids, saved views, filters, grouping, calculated fields, charts, dashboards, drilldown, schedules and PDF/Excel/CSV export. |
| 18 | Closeout | Missing explicit module | Add continuous Closeout module collecting approved records throughout execution and producing completeness dashboards and structured final packages. |
| 19 | Permissions | Strong partial | Core authorization architecture exists. Add admin permission preview/test: "What exactly can this person see/do?" with server-authoritative evaluation. |
| 20 | Implementation/configuration | Partial | Add Setup & Templates platform module for guided company setup, project/role/cost-code/workflow templates, imports, validation and configuration health checks. |
| 21 | Data ownership | Partial | Data Governance exists conceptually. Add explicit Data Portability/export service and release requirement for complete supported-record/file export without intentional lock-in. |
| 22 | Localization | Strong architectural coverage | Continue existing globalization/preferences design including historical currency/timezone/unit/rule preservation and jurisdiction-specific financial configuration boundaries. |
| 23 | Support & system health | Strong architectural coverage | Continue Admin Operations Center: app/database/storage/jobs/sync/email/backups/security/usage/errors plus plain-language Help/AI explanations. |
| 24 | AI | Strong architectural direction, not implemented | Keep AI optional and permission-scoped. Add specific use-case contracts. AI must not silently make financial, contractual, safety or approval decisions and should expose evidence where applicable. |
| 25 | Product quality rule | Strong coverage | Existing Module Contract Definition of Done remains mandatory: no fake counters, placeholder workflows, dead buttons or unsupported dashboard claims. |

## Additional platform modules required

The following shared capabilities must be added to `PLATFORM-MODULES.md` and implemented before dependent business modules are considered release-ready:

1. **Offline Sync & Device State** — encrypted local data, offline transaction queue, idempotency, retry, conflict resolution, acknowledgement, cache/package expiry and sync observability.
2. **Setup, Templates & Configuration Health** — guided onboarding, reusable project/role/workflow/cost-code templates, import validation and configuration diagnostics.
3. **Data Portability & Tenant Export** — complete authorized export orchestration for supported records, relationships and files, with manifests/checksums and auditable export jobs.

## Business modules that must become explicit

The full product module catalog must explicitly include at minimum:

- Drawings
- Specifications/Documents
- Estimating
- Takeoff
- Bid Management / External Collaboration
- RFIs
- Submittals
- Daily Reports / Field Operations
- Time & Workforce
- Scheduling
- Change Management
- Financials / Job Cost / Accounting
- Reporting
- Closeout

These business modules reuse platform Identity, Authorization, Feature Registry, Metadata, Workflow, Files, Integration, Jobs, Audit, Notifications, Search, Governance, Reporting projections, Help, Offline Sync and Data Portability rather than recreating those capabilities independently.

## Cross-cutting engineering gates

### Field usability

For field-heavy workflows, page contracts must document the primary user's fastest common path and expected interaction count. The least technical intended user should be able to complete the task without learning unrelated modules.

### Offline safety

Supported offline records must never disappear silently. Every offline mutation has a local durable identity, sync status and acknowledgement/error state. Conflict handling must preserve both sides until a deterministic rule or authorized user resolves the conflict.

### Performance budgets

Each performance-sensitive module must define measurable budgets before release and test against representative data volumes. Expensive pages must use pagination, projections, incremental loading, caching or background processing rather than unrestricted full-data loads.

### Data reuse

"Enter information once" is a design goal, but modules must not duplicate authoritative facts. Shared facts should be referenced or projected into downstream views. Derived records must identify their source and remain rebuildable where appropriate.

### Historical meaning

Configuration, workflow, exchange-rate, calculation, drawing revision and business-rule changes must preserve the historical context needed to explain old records. New configuration does not silently reinterpret completed historical business transactions.

### External collaboration

External/bidder access must be purpose-scoped, tenant-scoped, time-bound where appropriate, auditable and revocable. Temporary collaboration must not expose the broader Construction OS workspace.

### AI

AI remains optional. Core workflows continue to function without it. AI may assist, summarize, extract, classify, draft or highlight risk, but authoritative financial, contractual, safety and approval decisions remain deterministic/human-controlled unless a future explicitly reviewed policy says otherwise.

## Release rule

This baseline is part of the full-product release scope. A capability listed here can remain in `planned` feature state while being built, but it must not be represented to customers as available until its module contract, implementation, migration, security, tests, documentation and operational support are complete.
