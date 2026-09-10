# Construction OS Module Contract

Every business or platform module must maintain one module contract. This is the primary internal reference for design, implementation, security review, support and debugging.

## 1. Module identity

- Module name
- Module key
- Owner/bounded context
- Purpose
- Business problem solved
- Primary users
- Related modules
- Feature flag / tenant enablement key

## 2. Business terminology

Document the construction/accounting terminology used by the module, including alternate industry names where useful. Construction OS terminology must remain internally consistent and must not depend on a competitor's proprietary wording.

## 3. Objects

### System objects

Security/integrity fields and records that administrators cannot redefine.

### Admin objects

Tenant-configurable definitions such as types, classifications, custom fields, workflows, templates, numbering rules and policies.

### Business objects

Operational records created by users or system workflows.

For every object document:

- stable object key
- purpose
- tenant ownership
- lifecycle
- retention behavior
- soft-delete/archive behavior
- relationships
- core attributes
- configurable attributes
- sensitive attributes
- immutable attributes
- derived/calculated attributes
- concurrency/version field where concurrent or offline editing is possible

## 4. Page inventory

For each page/reference screen:

- page name
- route
- purpose
- primary object
- visible sections
- controls/actions
- filters/search/sort
- empty state
- loading/error states
- desktop/tablet/mobile behavior
- fastest common user path and expected interaction count for field-heavy tasks
- offline behavior if applicable
- realtime/live-update behavior if applicable
- help topic/context
- required feature
- required capabilities
- field-level visibility rules

Detailed pages follow `PAGE-CONTRACT.md`.

## 5. Permissions and access

Document:

- view/create/edit/delete/archive permissions
- workflow actions
- approval permissions
- export/download permissions
- sensitive-field permissions
- tenant scope
- project scope
- own/crew/assigned/all-company scope
- predefined-role defaults
- configurable-role behavior
- UI visibility behavior
- immediate permission-change behavior

Frontend visibility is never the security boundary; backend authorization is authoritative.

## 6. Workflow

Document:

- states
- allowed transitions
- transition permissions
- validation per transition
- notifications
- approvals
- rejection/reopen behavior
- workflow configuration options
- workflow versioning behavior
- historical-record behavior after workflow changes

## 7. Validation and business rules

For every significant rule record:

- rule name
- input
- output
- validation message
- configuration source
- server-side enforcement
- UI behavior
- versioning requirement
- historical-data impact

## 8. Data/schema design

Document:

- tables
- primary keys
- foreign keys
- tenant keys
- unique constraints
- indexes
- row-level security expectations
- JSON/custom metadata usage
- audit columns
- retention/archive approach
- expected record volume
- query/performance considerations
- optimistic-concurrency/version strategy where applicable

## 9. Compatibility and migration

Every module must comply with `docs/engineering/CHANGE-SAFETY.md`.

Record:

- schema version/change
- old behavior
- new behavior
- compatibility impact
- historical-data impact
- required backfill
- migration ID
- rollback/forward-fix approach
- known edge cases

## 10. Security and privacy

Document:

- data classification
- PII/financial/payroll/legal/safety sensitivity
- authorization boundary
- tenant-isolation checks
- file/storage access
- export exposure
- logging redaction
- audit requirements
- step-up MFA requirements
- rate-limit/abuse considerations
- AI access allowed/restricted/prohibited
- offline-device exposure and local-data sensitivity where applicable
- realtime-event payload restrictions where applicable

## 11. Audit events

List every auditable action, including:

- actor
- organization
- project/resource scope
- action
- old/new value where appropriate
- timestamp
- session/correlation ID
- reason when required

## 12. Notifications

Document events that can generate:

- in-app notifications
- email
- push/mobile notifications
- escalation/reminders

Notification content must respect the recipient's permissions and must not leak sensitive data through subject lines or previews.

## 13. Realtime, offline and client state

For any module affected by concurrent edits, field connectivity or live collaboration, document:

- events emitted after committed mutations;
- event type, entity version and required capability/scope;
- client cache entries invalidated/refreshed by each event;
- reconnect/catch-up behavior;
- offline-capable records/actions;
- local queue behavior and client-generated mutation IDs;
- idempotency behavior on retry;
- conflict detection and resolution rules;
- server acknowledgement semantics;
- what happens when the cursor/event-retention window has expired;
- device revocation/security behavior;
- data that must never be placed inside event or sync diagnostics payloads.

Realtime delivery must not become a second authorization path. Offline support must not silently lose entered information.

## 14. Performance budgets

For performance-sensitive modules, define measurable targets using representative data volumes for:

- first useful page content;
- common reads/saves;
- search/filtering;
- project/context switching;
- scrolling/list virtualization where applicable;
- realtime propagation;
- offline local save and reconnect start;
- heavy background operations;
- drawing/document rendering where applicable.

Document pagination, incremental loading, caching/projections and background processing used to stay within these budgets. Do not accept unrestricted full-table/full-file loading as a normal implementation shortcut.

## 15. Reporting and exports

Document:

- dashboard metrics
- standard reports
- configurable reports
- export formats
- permission requirements
- historical calculations
- timezone/currency handling

## 16. Help and knowledge

Each page/module must include concise authenticated help content:

- what the module does
- common workflows
- field definitions
- permission explanations
- troubleshooting
- FAQ

The optional local/help AI consumes this approved knowledge and page context rather than inventing product behavior.

## 17. Testing

Required test categories as applicable:

- unit
- API/integration
- authorization
- cross-tenant isolation
- migration/backward compatibility
- workflow
- UI/responsive
- accessibility
- offline/sync
- realtime reconnect/catch-up
- duplicate/idempotent retry
- concurrency/conflict
- performance
- security/regression

## 18. Observability and debugging

Document:

- health indicators
- structured log events
- metrics
- traces/correlation IDs
- realtime backlog/lag where applicable
- offline sync/conflict counts where applicable
- common failure modes
- expected error codes
- diagnostic queries/tools
- safe support procedures

Never require unrestricted access to tenant data for routine troubleshooting.

## 19. Change history and impact register

Maintain a chronological internal table for significant changes:

| Release | Change | Schema/Migration | Existing Data Impact | Permission Impact | Risk | Rollback/Recovery | Notes |
|---|---|---|---|---|---|---|---|

Do not remove old entries when behavior changes again. This register is part of the debugging history.

## 20. Definition of done

A module/feature is complete only when its real persistence, validation, authorization, tenant isolation, audit, error states, responsive UI, search/filtering, realtime behavior where relevant, offline behavior where relevant, performance budgets, tests, documentation, migration/compatibility behavior, real dashboard/report integration and operational diagnostics are implemented.

Empty UI shells, fake counters, placeholder workflows, dead buttons, silent last-write-wins conflicts, undocumented hardcoded business values and unsupported dashboard claims do not count as completed features.

## 21. Configuration manifest

Every future business module must register its supported configuration surface with the shared Company/App Configuration foundation before customer-specific form or workflow behavior is implemented.

The module contract must list:

- standard sections and standard fields owned by the product;
- stable configuration keys owned by the module;
- platform defaults;
- value type and validation for each key;
- whether each key is protected, business-configurable or a user preference;
- allowed override scopes: company, project template, project and/or user preference;
- change classification: presentation, metadata, business rule, workflow, financial or security;
- historical behavior and whether records must pin a configuration/rule version;
- whether the setting affects offline packages or queued offline mutations;
- relevant feature/capability requirements;
- supported custom-field entity types;
- supported workflow hooks;
- notification events/preferences used;
- attachment/file support;
- search projection provider;
- reporting dataset/provider;
- import/export provider;
- retention/governance behavior;
- realtime invalidation behavior;
- configuration-health checks.

Business modules must consume the shared effective-configuration resolver and the existing shared platform engines. They must not create private copies of authorization, custom-field, workflow, notification, audit, file, search, reporting, realtime, offline, template or retention infrastructure.

A module may expose a simple configuration for a small contractor and a richer configuration for an enterprise, but both must execute through the same canonical business engine and object model.
