# Construction OS Data Architecture

## Goal

Construction OS must handle structured business records, dynamic tenant-defined metadata, images and documents, audit history, search and reporting without creating performance bottlenecks or sacrificing tenant isolation.

The data architecture uses the right store for each workload rather than placing everything in one database.

## Storage model

### 1. PostgreSQL — transactional source of truth

Use PostgreSQL for business and system records that require strong consistency, relationships, constraints, transactions, permissions and auditability.

Examples:
- organizations and memberships
- users and security identities
- projects
- people, workers and crews
- RFIs and submittals
- schedules and tasks
- budgets and financial records
- payroll and accounting records
- role/permission assignments
- workflow state
- custom-field definitions
- attachment metadata
- audit references

Core business relationships must remain relational. JSON must not replace well-defined relational columns simply for convenience.

### 2. Object storage — binary/file content

Do not store large images, PDFs, drawings, videos or other binaries directly inside transactional PostgreSQL tables.

Store file bytes in a private object-storage layer and store only metadata/references in PostgreSQL.

Example file metadata:
- id
- organization_id
- project_id nullable
- owning_object_type
- owning_object_id
- original_file_name
- storage_key
- content_type
- byte_size
- checksum
- upload_status
- security_classification
- created_by
- created_at
- deleted_at nullable

The physical storage key must not itself grant access.

All file access must pass authenticated tenant/resource authorization before a short-lived download/upload authorization is issued.

### 3. Flexible attributes — metadata engine

Tenant-defined custom fields are stored through a controlled metadata layer.

A field definition contains:
- tenant
- target object/module
- immutable internal key
- display label
- field type
- validation
- required/optional state
- search/filter/report behavior
- display order
- permissions
- active/deactivated state
- configuration version

Values may use typed relational value tables or JSONB depending on workload, but:
- identifiers remain stable when labels change
- historical values are preserved when fields are deactivated
- field type changes require compatibility analysis
- frequently filtered/reportable attributes require appropriate indexes or projections

Do not use a completely free-form schema for security, finance, tenancy or core construction relationships.

## Database selection rule

Adding a non-relational database is not a default requirement.

Use another datastore only when a measured workload cannot be served efficiently by PostgreSQL/object storage/search infrastructure.

Examples of justified future additions:
- Redis-compatible cache for ephemeral/cache/session coordination
- dedicated full-text/search engine for very large document/project search workloads
- analytics warehouse for heavy cross-tenant/long-range analytical workloads using privacy-safe replicated data
- time-series store only if equipment/telemetry volume proves PostgreSQL insufficient

Every new datastore increases:
- security surface
- backup/restore complexity
- operations burden
- consistency problems
- deployment complexity

Therefore new persistence technology requires an impact assessment.

## Images and media

Construction OS must expect high-volume mobile image uploads.

Upload pipeline:

1. client requests upload authorization
2. API verifies authenticated session, tenant and object permission
3. server creates a pending attachment record
4. client uploads bytes to private object storage using short-lived authorization
5. asynchronous worker validates completion
6. malware/content checks run where applicable
7. checksum and metadata are persisted
8. thumbnails/previews are generated asynchronously
9. attachment becomes available to authorized users

The API process must not hold large media uploads in memory when direct private-storage upload is available.

Generate multiple representations where useful:
- original
- thumbnail
- preview/medium image

Do not repeatedly resize the original during normal page loads.

## Performance principles

### Keep list endpoints light

Project lists and dashboards must not fetch full comments, images, audit trails or document bodies.

Use summary/projection queries and fetch details only when opened.

### Pagination everywhere

Potentially unbounded collections must use pagination/cursors:
- projects
- users
- daily logs
- RFIs
- attachments
- audit events
- invoices
- notifications

Never load an entire tenant dataset into the browser.

### Index deliberately

Index columns based on actual access patterns, especially combinations such as:
- organization_id + id
- organization_id + status
- organization_id + project_id
- organization_id + created_at
- project_id + status
- foreign-key columns

Tenant identity must be part of relevant index/query design.

Avoid indiscriminate indexes because write-heavy construction workflows can suffer from excessive index maintenance.

### Avoid N+1 querying

API/service queries must fetch related data deliberately. Module performance tests should detect regressions where list endpoints issue per-row database queries.

### Derived data

Expensive dashboard totals, search indexes, thumbnails and report projections may be generated asynchronously.

Transactional tables remain the source of truth. Derived data must be rebuildable.

### Background jobs

Use durable background jobs/outbox events for work such as:
- image preview generation
- virus/malware scanning
- report/PDF generation
- document extraction
- notifications
- exports
- search indexing
- large imports/migrations

HTTP request latency must not depend on completing these tasks synchronously unless the user operation truly requires it.

## Multi-tenant isolation

Tenant context applies to every persistence surface:
- PostgreSQL
- object storage
- caches
- search indexes
- queues/jobs
- exports
- temporary files
- analytics replicas
- backups
- AI context

A storage key, database primary key or search document id must never be treated as authorization.

Every read/write is authorized independently.

## Audit data

Audit history is append-oriented and separate from normal editable business fields.

Audit records should capture:
- organization
- actor/user/service
- action
- object type/id
- timestamp
- correlation/request id
- before/after references or safe change representation
- security context where appropriate

High-volume audit data may later be partitioned/archived while remaining queryable according to retention requirements.

Audit retention must not be silently coupled to deletion of the business object.

## Deletion and retention

Differentiate:
- active
- archived
- soft-deleted
- legally/operationally retained
- permanently purged

Deleting a UI record must not automatically purge associated audit, financial or regulated history.

File deletion uses the same controlled lifecycle and must handle derived thumbnails/previews safely.

Retention policy is tenant configurable only within platform/legal safeguards.

## Backward-compatible schema evolution

Database migrations are versioned and reviewed under the Change Safety standard.

Preferred changes:
- additive tables
- additive nullable columns
- compatible indexes
- new versioned configuration

Riskier changes require migration plans:
- column type changes
- destructive column/table removal
- changing historical semantics
- required columns without safe historical values
- rewriting financial/payroll records
- changing custom-field types

Use expand/migrate/contract patterns for significant production changes rather than destructive one-step migrations.

## Reporting and analytics

Operational pages read transactional/projection data optimized for current work.

Heavy historical analytics must not be allowed to degrade normal field/project workflows.

As volume grows, reporting can use:
- read replicas
- materialized/projection tables
- asynchronous report generation
- dedicated analytics storage when justified

Cross-tenant analytics must never expose tenant-identifiable data without explicit platform policy and authorization.

## Data portability

Construction OS data must remain exportable through controlled, permissioned mechanisms.

Exports:
- are tenant scoped
- are audited
- may require step-up authentication for sensitive data
- execute asynchronously when large
- expire after a limited download period

Migration/import frameworks use canonical internal object contracts and never bypass validation, tenancy or audit controls.

## Observability

Each data-intensive module should define performance targets and telemetry for:
- API latency
- database query duration
- rows scanned/returned
- object upload latency
- background job delay
- error rate
- storage failures
- cache/search rebuild failures

Do not log sensitive business payloads solely for debugging.

## Guiding rule

Structured business truth belongs in relational storage; large binary content belongs in private object storage; flexible tenant metadata is controlled and typed; derived stores exist for performance but are rebuildable.

No datastore may become a security shortcut or a second uncontrolled source of truth.
