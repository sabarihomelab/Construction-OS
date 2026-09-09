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
- offline behavior if applicable
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

## 13. Reporting and exports

Document:

- dashboard metrics
- standard reports
- configurable reports
- export formats
- permission requirements
- historical calculations
- timezone/currency handling

## 14. Help and knowledge

Each page/module must include concise authenticated help content:

- what the module does
- common workflows
- field definitions
- permission explanations
- troubleshooting
- FAQ

The optional local/help AI consumes this approved knowledge and page context rather than inventing product behavior.

## 15. Testing

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
- performance
- security/regression

## 16. Observability and debugging

Document:

- health indicators
- structured log events
- metrics
- traces/correlation IDs
- common failure modes
- expected error codes
- diagnostic queries/tools
- safe support procedures

Never require unrestricted access to tenant data for routine troubleshooting.

## 17. Change history and impact register

Maintain a chronological internal table for significant changes:

| Release | Change | Schema/Migration | Existing Data Impact | Permission Impact | Risk | Rollback/Recovery | Notes |
|---|---|---|---|---|---|---|---|

Do not remove old entries when behavior changes again. This register is part of the debugging history.

## 18. Definition of done

A module/feature is complete only when its real persistence, validation, authorization, audit, error states, responsive UI, tests, documentation, migration/compatibility behavior and operational diagnostics are implemented. Empty UI shells, fake counters, placeholder controls and undocumented hardcoded business values do not count as completed features.
