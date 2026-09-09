# Construction OS Storage Capacity and Governance

## Design goal

Construction OS is designed to operate efficiently within an initial storage envelope of approximately 2 TB while remaining horizontally extensible beyond that capacity. The 2 TB target is an operating baseline, not a product ceiling.

## Storage classes

1. **Transactional data** — PostgreSQL. Structured business records, identities, permissions, workflows, audit metadata, integration mappings and file metadata.
2. **Object data** — private object storage. Photos, videos, PDFs, drawings, contracts, receipts, exports and other binary files.
3. **Derived data** — thumbnails, previews, temporary exports, caches, indexes and analytics projections. These must always be rebuildable and must never become the only copy of authoritative business data.

## Capacity principles

- Do not store binary files inside PostgreSQL except for very small system artifacts where there is a documented reason.
- Preserve the original uploaded file when required for legal, contractual or evidentiary purposes.
- Generate appropriately sized previews and thumbnails for UI use rather than repeatedly serving originals.
- Apply compression only where it does not alter required evidentiary or source quality.
- Deduplicate physical object bytes within a tenant when the checksum and retention policy permit it. Never allow cross-tenant deduplication to weaken isolation.
- Delete abandoned multipart uploads, failed processing artifacts and temporary exports automatically after a configured retention period.
- Keep storage accounting per tenant, project, module, media type and storage class.

## Tenant quotas

Each tenant may have a configurable storage entitlement. Quotas control new storage consumption but do not make existing records inaccessible.

Recommended warning stages:

- 70% — informational capacity warning
- 85% — administrator warning and capacity planning prompt
- 95% — critical warning; restrict non-essential bulk imports where policy allows
- 100% — preserve existing data and reads; reject new storage-heavy writes with a clear administrative resolution path

Exact thresholds must remain configurable by deployment policy.

## Retention and lifecycle

Retention must be configurable by tenant, module and record type within system safety limits. Examples include active project media, completed-project records, audit history, temporary exports and integration staging data.

Historical business records must not be deleted merely because a lifecycle policy changes. Destructive retention rules require explicit authorization, audit logging and documented recovery/backup behavior.

## File versions

Where versioning is meaningful (drawings, contracts, specifications, controlled documents), new versions are separate immutable file objects linked to one logical document record. The system must not silently replace an earlier version.

## External application ingestion

Files imported from external applications are copied into Construction OS private storage after validation. Source URL, provider, external identifier, source version, checksum, ingestion timestamp and mapping version are recorded so the imported artifact can be traced without depending permanently on the external URL.

## Performance rules

- File transfers should use private object-storage upload/download paths rather than proxying large payloads through the application API when possible.
- UI lists use thumbnails/previews and pagination.
- Background workers handle malware scanning, preview generation, metadata extraction and heavy imports.
- PostgreSQL queries never scan object bytes.
- Large audit/activity tables may use partitioning and archival policies.
- Storage usage calculations are maintained incrementally rather than recomputing all object sizes on every dashboard request.

## Expansion beyond 2 TB

The storage layer must be abstracted so capacity can be expanded without changing business modules. Supported future patterns may include:

- additional disks/nodes in self-hosted object storage;
- larger dedicated object-storage clusters;
- cloud-compatible object storage;
- dedicated storage per enterprise tenant;
- customer-managed storage where contractual requirements require it.

Moving or expanding storage must preserve stable attachment identities. Business records reference logical storage objects, not hard-coded physical disk paths.

## Operational monitoring

Track at minimum:

- total provisioned capacity;
- total used and available capacity;
- usage by tenant;
- usage by project/module/media type;
- growth rate;
- largest objects;
- orphaned objects;
- failed/abandoned uploads;
- temporary/derived data usage;
- backup footprint and retention;
- object-store health and replication state.

Storage-capacity changes, quota changes, retention-rule changes and destructive cleanup operations must be audited.
