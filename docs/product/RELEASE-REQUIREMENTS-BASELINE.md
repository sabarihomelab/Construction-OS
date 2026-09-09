# Construction OS Full Product Release Requirements Baseline

This document converts recurring construction-user feedback into an explicit Construction OS **Release 1 acceptance baseline**. It supplements module contracts and architecture standards; it does not replace them.

## Release interpretation

All 25 requirement areas in this baseline are in scope for the first production release. They may remain in internal `planned`/`preview` states while being built, but Release 1 is not considered complete until every applicable area is addressed with a production-usable implementation or an explicitly documented jurisdiction-dependent boundary.

Construction OS must not claim a capability is released until it satisfies the module Definition of Done: real persistence, validation, authorization, tenant isolation, error handling, audit where relevant, responsive/mobile behavior, offline behavior where required, realtime behavior where relevant, search/filtering, tests, documentation and real dashboard/report integration.

Country-specific statutory tax/payroll calculations remain the one intentional boundary: the core payroll/accounting framework is Release 1 scope, while jurisdiction packages require a defined target country/region before compliance can be claimed.

## Coverage matrix

| # | Requirement | Current coverage | Release 1 action |
|---|---|---|---|
| 1 | Field-first UX | Partial | Deliver field-task UX standards: minimal taps, role/task-specific layouts, large touch targets, carry-forward, responsive mobile behavior and low-training workflows. |
| 2 | Offline-first mobile | Partial | Deliver Offline Sync & Device State with encrypted local storage, durable mutation queue, retry, conflict handling, acknowledgement and visible sync status for supported field workflows. |
| 3 | Performance is a feature | Partial | Define and test measurable performance budgets for startup/login, project switching, drawings, search, scrolling, saves, sync, realtime propagation and dashboards. |
| 4 | Global search | Partial | Deliver Search & Indexing across all supported business objects, module search/filtering and preservation of navigation/search state. |
| 5 | Drawing engine | Missing explicit business module | Deliver Drawings module/engine for sets, sheets, revisions, overlays/comparison, markups, measurements, calibration, pins, offline packages and fast mobile rendering. |
| 6 | Estimating engine | Missing explicit business module | Deliver Estimating and Takeoff with structured spreadsheet-like calculations, formulas, assemblies, resources, versions, comparison, cost codes and first-class Excel import/export. |
| 7 | Scope intelligence | Partial/future AI | Deliver evidence-based estimating intelligence for drawing/spec comparison, scope gaps, bid exclusions and revision differences. AI suggests; human confirms. |
| 8 | Bidder/external collaborator experience | Partial | Deliver temporary/scoped external collaboration plus Bid Management/External Collaboration without requiring unnecessary full-workspace accounts/seats. |
| 9 | RFIs | Planned, not fully contracted | Deliver complete RFI workflow with drawing/spec/location/schedule/cost links, due dates, reminders, escalation, ball-in-court and history. |
| 10 | Submittals | Planned, not fully contracted | Deliver Package -> Items -> Revisions model with workflow/attachments and specification/drawing/procurement/schedule/lead-time links. |
| 11 | Notification engine | Partial | Deliver priority taxonomy, reason-for-notification, preferences, channels, quiet hours, digests, escalation, subscriptions and realtime/in-app state. |
| 12 | Daily report / field data | Partial | Deliver crews, carry-forward, voice, photos, weather, manpower, equipment, deliveries, production, delays, visitors, safety, T&M and downstream reuse without duplicate entry. |
| 13 | Time & workforce | Partial | Deliver internal/subcontract labor, crews, time types, cost codes, location, equipment, production, approvals, obvious task/project switching and offline entry. |
| 14 | Scheduling | Missing detailed contract | Deliver activities, dependencies, milestones, critical path, baselines, look-aheads, constraints, calendars, actuals, delays and procurement/submittal integration with simple field progress updates. |
| 15 | Change management | Missing detailed contract | Deliver connected Potential Issue -> Change Event -> Cost/Quantity -> RFQ -> Quote -> Review -> Owner Change -> Commitment -> Budget/Job Cost -> Billing chain. |
| 16 | Native construction financials | Partial/high-level | Deliver COA, cost codes, jobs, budgets, commitments, POs, AP, AR, progress billing, retainage, change orders, payroll core, job cost, GL, cash, equipment costing and financial reporting. Jurisdiction-specific statutory calculations remain configurable packages. |
| 17 | Reporting | Partial | Deliver configurable grids, saved views, filters, grouping, calculated fields, charts, dashboards, drilldown, scheduled reports and PDF/Excel/CSV export. |
| 18 | Closeout | Missing explicit business module | Deliver continuous Closeout collecting approved records during project execution, completeness dashboards and structured final packages. |
| 19 | Permissions | Strong partial | Complete role templates, granular permissions, scopes and admin permission preview/test: "What exactly can this person see/do?" with server-authoritative evaluation. |
| 20 | Implementation/configuration | Partial | Deliver guided company setup, project/role/cost-code/workflow templates, imports, validation and configuration health checks without consultant dependence. |
| 21 | Data ownership | Partial | Deliver complete authorized export for supported records/files/relationships without intentional lock-in, plus audit/manifest/versioning for large exports. |
| 22 | Localization | Strong architectural coverage | Implement language/locale/currency/number/date/timezone/units/tax configuration and historical currency/timezone/unit/rule preservation. |
| 23 | Support & system health | Strong architectural coverage | Deliver Admin Operations Center covering app/database/storage/jobs/sync/email/backups/security/usage/errors plus plain-language Help/AI explanations. |
| 24 | AI | Strong architectural direction, not implemented | Deliver optional permission-scoped AI assistance for defined use cases; AI never silently decides financial, contractual, safety or approval outcomes and exposes evidence where applicable. |
| 25 | Product quality rule | Strong coverage | Enforce Definition of Done: no fake counters, placeholder workflows, dead buttons or unsupported dashboard claims. |

## Additional platform modules required

The following shared capabilities are Release 1 dependencies and must be implemented before dependent business modules are considered release-ready:

1. **Offline Sync & Device State** — encrypted local data, offline transaction queue, idempotency, retry, conflict resolution, acknowledgement, cache/package expiry and sync observability.
2. **Setup, Templates & Configuration Health** — guided onboarding, reusable project/role/workflow/cost-code templates, import validation and configuration diagnostics.
3. **Data Portability & Tenant Export** — complete authorized export orchestration for supported records, relationships and files, with manifests/checksums and auditable export jobs.
4. **Real-Time Events & Client State** — committed-event delivery, tenant/permission scoping, reconnect/catch-up cursors, targeted UI invalidation and live updates without making websocket state authoritative.

## Business modules that must become explicit

The Release 1 module catalog must explicitly include at minimum:

- Projects
- Drawings
- Specifications/Documents
- Estimating
- Takeoff
- Bid Management / External Collaboration
- RFIs
- Submittals
- Meetings
- Daily Reports / Field Operations
- Photos
- Time & Workforce
- Safety
- Inspections
- Punch
- Equipment
- Materials
- Scheduling
- Change Management
- Financials / Job Cost / Accounting
- Reporting
- Closeout

These business modules reuse platform Identity, Authorization, Feature Registry, Metadata, Workflow, Files, Integration, Jobs/Outbox, Audit, Notifications, Search, Governance, Reporting projections, Help, Offline Sync, Realtime Events and Data Portability rather than recreating those capabilities independently.

## Cross-cutting engineering gates

### Field usability

For field-heavy workflows, page contracts must document the primary user's fastest common path and expected interaction count. The least technical intended user should be able to complete the task without learning unrelated modules.

### Offline safety

Supported offline records must never disappear silently. Every offline mutation has a local durable identity, sync status and acknowledgement/error state. Conflict handling must preserve both sides until a deterministic rule or authorized user resolves the conflict.

### Realtime consistency

Committed business state is authoritative. Realtime events notify/refresh clients after commit; they are not the source of truth. Reconnecting clients use durable cursors/revisions to catch up on missed changes. Sensitive payloads are not broadly broadcast; clients refetch through authorized APIs.

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

**Release 1 addresses all 25 requirement areas in this baseline.** Internal development may progress module-by-module and features may remain hidden while incomplete, but the first production release is not declared complete until the applicable module contracts, persistence, migrations, security, tenant isolation, responsive/offline/realtime behavior, tests, documentation, observability and operational support are complete.
