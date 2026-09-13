# Construction OS Storage Capacity and Governance

## Design goal

Construction OS has no fixed product-level storage ceiling. Storage capacity is determined by the deployment architecture, infrastructure provisioned for that environment, and optional tenant/company policy.

The application must remain storage-efficient, observable and expandable. Increasing storage capacity must not require redesigning business modules or changing attachment identities.

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
- Business modules must reference logical storage identities rather than physical disk/container/provider locations.

## Tenant quotas and capacity policies

Storage quotas are optional policy controls, not architectural limits.

A deployment may operate with:

- no tenant quota;
- a company-specific quota;
- a plan/contract entitlement;
- dedicated storage capacity;
- customer-managed storage capacity.

Where quotas are enabled, they control new storage consumption but never make existing records inaccessible merely because a threshold is reached.

Recommended warning stages, when a quota/capacity policy exists:

- 70% — informational capacity warning;
- 85% — administrator warning and capacity-planning prompt;
- 95% — critical warning;
- 100% — preserve existing reads/data and reject only new storage-consuming operations that cannot be accommodated, with a clear administrative resolution path.

Thresholds remain configurable by deployment/company policy.

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
- Drawings and other very large documents use optimized/tiled/derived representations where required for responsive viewing; originals remain independently managed.

## Expansion and scale

The storage layer must be abstracted so capacity can expand without changing business modules. Supported deployment patterns may include:

- additional disks/nodes in self-hosted object storage;
- larger dedicated object-storage clusters;
- cloud-compatible object storage;
- dedicated storage per enterprise tenant;
- customer-managed storage where contractual requirements require it;
- migration between storage providers through controlled background operations.

Moving or expanding storage must preserve stable attachment identities. Business records reference logical storage objects, not hard-coded physical disk paths.

## Operational monitoring

Track at minimum:

- total provisioned capacity where measurable;
- total used and available capacity;
- optional quota/entitlement and utilization percentage;
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
