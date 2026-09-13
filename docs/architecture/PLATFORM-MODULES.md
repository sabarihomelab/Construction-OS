# Construction OS Platform Modules

These modules support all business applications. They are product infrastructure, not customer-facing construction modules by themselves.

## 1. Tenant and Organization
Owns tenant identity, company settings, plan/feature configuration, tenant status and isolation boundaries.

## 2. Identity and Session
Owns authentication, MFA/passkeys, secure sessions, idle/absolute expiry, recovery, device/session revocation and login security.

## 3. Authorization
Owns roles, capabilities, scopes, project access, sensitive-data permissions, effective access calculation and permission-driven UI context.

## 4. Feature Registry
Owns product modules/features, navigation metadata, required capabilities, company enablement and release state.

## 5. Object and Metadata Engine
Owns system/admin/business object definitions, custom fields, field validation, labels, display rules and configuration versioning.

## 6. Workflow and Approval Engine
Owns configurable states, transitions, approvals, step-up requirements, assignees, due rules and workflow version history.

## 7. File and Media Service
Owns attachments, private object storage, file metadata, checksums, versions, previews, thumbnails, malware-scan status, retention and permission-controlled delivery.

## 8. Integration Gateway
Owns external-system connectors, credentials references, rate limiting, source-system identity, inbound/outbound contracts and connector health.

## 9. Ingestion and Staging
External data never writes directly to business tables. Ingestion owns validation, staging, quarantine, normalization, duplicate detection and commit readiness.

## 10. Mapping and Transformation
Owns field mappings between external records and Construction OS canonical objects, configurable mapping rules, transformation versions and mapping diagnostics.

## 11. Synchronization and Reconciliation
Owns external identifiers, source versions, checkpoints/cursors, idempotency, conflict detection, retry state, reconciliation and sync history.

## 12. Background Jobs and Event Outbox
Owns durable asynchronous work such as image processing, external fetches, notifications, report generation, sync, indexing and long-running tasks. The transactional outbox is the durable bridge between committed business changes and asynchronous/realtime delivery.

## 13. Audit and Change History
Owns immutable security/business audit events, configuration change history, actor/session/correlation identifiers and traceability.

## 14. Notifications
Owns in-app/email/push delivery, preferences, templates, delivery attempts and tenant-aware routing.

## 15. Search and Indexing
Owns derived searchable projections while PostgreSQL remains source of truth. Search indexes must be tenant-scoped and rebuildable.

## 16. Help and Knowledge
Owns authenticated page help, product documentation, page context, company-specific configuration help and future private/local help assistant context.

## 17. Data Governance
Owns retention policies, archival, legal holds where needed, export policy, deletion policy, data classification and lifecycle rules.

## 18. Observability and Support Diagnostics
Owns health checks, structured logs, correlation IDs, metrics, error diagnostics, support bundles and privacy-safe troubleshooting information.

## 19. Reporting and Analytics Projection
Owns derived summaries, reporting projections and future analytical stores so heavy reporting does not overload transactional paths.

## 20. API and Contract Versioning
Owns public/internal API versions, compatibility windows, deprecation rules and schema-contract evolution.

## 21. Offline Sync and Device State
Owns supported offline data packages, encrypted local device state, durable offline mutation queues, client-generated idempotency keys, visible sync status, automatic retry, conflict detection/resolution, server acknowledgement, cache/package expiry and sync diagnostics. Offline-capable modules must use this shared mechanism rather than creating their own local persistence/synchronization behavior.

## 22. Setup, Templates and Configuration Health
Owns guided company setup, project templates, role templates, workflow templates, cost-code/classification templates, reusable configuration packages, import validation, configuration dependency checks and plain-language configuration health diagnostics. Setup must create real tenant data and must not seed fake business records.

## 23. Data Portability and Tenant Export
Owns authorized full-tenant and scoped export orchestration for supported records, relationships and files. Exports use stable schemas/manifests, explicit canonical identifiers, checksums where useful, background jobs for large packages, permission checks, audit events and predictable versioned formats. Construction OS must not intentionally use proprietary storage representations to trap customer-owned data.

## 24. Real-Time Events and Client State
Owns permission-scoped realtime change delivery to connected clients, reconnect/catch-up semantics, event cursors, client-state invalidation and live UI refresh. PostgreSQL remains authoritative: realtime events are emitted only from committed changes, normally through the transactional outbox. A disconnected client must be able to reconnect and obtain changes since its last acknowledged cursor without relying on an in-memory websocket message history.

Realtime delivery must be tenant-scoped and authorization-aware. Events contain minimal identifiers/revisions needed to refresh affected state; sensitive business payloads are fetched again through normal authorized APIs rather than broadcast indiscriminately.

## Architectural rule
Business modules use these platform services through stable internal interfaces. No business module should independently implement authentication, file storage, external synchronization, audit, custom fields, offline synchronization, realtime delivery, tenant export or background-job infrastructure.
