# Daily Reports / Field Operations

## Purpose

Daily Reports provide a fast, project-scoped record of field activity while supporting both small contractors and enterprise controls through the shared Construction OS configuration platform.

There is one Daily Report engine. Companies do not receive separate small-business and enterprise implementations.

## Configuration model

The module consumes effective configuration using the standard hierarchy:

`Platform Default -> Company -> Project Template -> Project -> User Preference`

Initial registered business settings include:

- enabled standard sections
- required standard sections
- whether approval is required
- shared Workflow definition key for approval
- carry-forward behavior
- default shift

Initial personal preferences include compact entry and visible list columns. Personal preferences are presentation-only and cannot change submission or approval rules.

The default experience is intentionally small: Crew, Work, Photos and Notes are enabled, with Work required for submission. An enterprise can enable Weather, Equipment, Deliveries, Production, Delays and Safety without changing the module implementation.

## Standard sections

The protected section vocabulary is:

- Weather
- Crew
- Work
- Equipment
- Deliveries
- Production
- Delays
- Safety
- Photos
- Notes

Core construction data is stored in typed relational fields. Additional tenant-specific attributes use the shared Metadata / Custom Fields engine rather than adding arbitrary columns or a module-specific EAV system.

Photos and attachments use File & Media links. Safety records may later link to the dedicated Safety engine rather than duplicating incident/inspection state inside the Daily Report.

## Lifecycle

The initial domain states are Draft, Submitted/In Review, Approved, Rejected and Void.

Draft data is editable with optimistic revision checking. Material changes increment the report revision. A stale client must refresh rather than silently overwrite newer field data.

Submission resolves current effective configuration, verifies that required sections are enabled and contain data, and stores a compact configuration context required to preserve historical meaning. It does not snapshot the entire company configuration.

When approval is configured, the authoritative approval route must use the shared Workflow / Approval engine. Daily Reports must not grow a separate workflow-definition system.

Rejected reports may be reopened as a new draft revision. Void is a controlled historical state and does not physically delete the report.

## Historical configuration safety

At submission, the report preserves only the policy context that can affect interpretation, including:

- configuration revision tokens
- project-template version reference
- enabled sections
- required sections
- approval requirement
- effective timestamp

Later company or project configuration changes therefore do not silently reinterpret an already-submitted report.

Typed business values remain on the report/section records. Configuration history remains in the shared configuration engine.

## Authorization

Project scope and backend permissions remain authoritative. Initial capabilities are:

- `field.daily_report.view`
- `field.daily_report.create`
- `field.daily_report.update`
- `field.daily_report.submit`
- `field.daily_report.approve`
- `field.daily_report.manage`

The browser never supplies organization ownership. The organization comes from the authenticated session and the project comes from an authorized project route.

## Shared platform integrations

Daily Reports reuse, rather than reimplement:

- Feature Registry for module availability
- Authorization for company/project capabilities
- Configuration Resolver for effective form/business settings
- Metadata for custom fields
- Workflow / Approval for enterprise approval routes
- File & Media for photos and attachments
- Audit for material actions
- Notifications for reminders/approval events
- Search for project-scoped discovery
- Reporting for approved datasets and exports
- Realtime Events for targeted updates
- Offline Sync for future durable field capture
- Localization for timezone, units and terminology
- Integration/Ingestion for external imports/exports
- Data Governance for retention/legal holds

## Realtime and search

Daily Report changes emit project-scoped events carrying only minimal state. Search uses the shared projection provider registry with `field.daily_report.view` and project scope.

Normal saves do not rebuild a project dashboard or download unrelated company configuration.

## Performance and field UX

The least technical field user is the design baseline. The normal path should prioritize today's report, large touch targets, minimal typing, carry-forward where safe, fast photo capture, clear save/sync state and immediate local feedback.

A company enabling many other Construction OS modules must not make Daily Report entry slower. Only Field configuration and authorized project data should be loaded for this task.

## Offline contract

Release 1 field use must support durable encrypted local drafts/mutations, idempotent sync, entity revision conflict detection, photo upload recovery and visible sync state. Material conflicts must not use silent last-write-wins.

The server-side entity revision and shared offline foundation are already prepared for this behavior; the client offline store/queue remains Release 1 implementation work.

## Release 1 work still required

This backend foundation does not by itself make the module production-complete. Remaining Release 1 work includes:

- complete binding of approval-required submission to published shared Workflow definitions and approval tasks
- responsive/PWA Daily Report UI driven by effective configuration
- offline local database, queue, retry and conflict-resolution experience
- photo capture/upload/preview integration through File & Media
- safe carry-forward implementation
- Custom Field rendering/value integration
- notification rules/reminders through the shared Notification engine
- Workforce, Equipment, Materials and Scheduling links as those domain engines are built
- Reporting dataset/export providers
- import/export adapters where required
- configuration-health validation for cross-setting rules such as required sections being enabled
- performance/load tests and field interaction-count validation
- full integration/API/tenant-isolation tests

The Feature Registry remains `PLANNED` until the Release 1 user experience and operational requirements are complete.
