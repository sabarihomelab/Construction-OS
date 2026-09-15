# File and Media Service

## Purpose

Provide one secure, tenant-safe file foundation for every Construction OS business module: drawings, specifications, RFIs, submittals, daily reports, photos, estimating/takeoff, bidder packages, inspections, safety, financial attachments and closeout.

Business modules never implement their own storage URLs, upload buckets, file-version tables or download authorization.

## Core model

```text
Storage Object
    physical immutable bytes in private object storage

File Asset
    logical file/document identity visible to the product

File Version
    immutable version of a logical asset

File Link
    relationship from a business object to an asset/version

File Variant
    rebuildable thumbnail/preview/rendering derivative
```

This separation allows document versioning and deduplication without changing business-record identities.

## Storage provider abstraction

Business logic depends on `StorageProvider`, not S3/Azure/local paths.

The provider contract owns:

- private upload target creation;
- object inspection/checksum/size metadata;
- short-lived download targets;
- deletion of storage objects.

Adapters may later target open-source S3-compatible storage, dedicated/private storage, public cloud object storage or customer-managed storage without changing business modules.

## No fixed product capacity ceiling

Construction OS has no fixed product-level storage ceiling. `organization_settings.storage_quota_bytes` is nullable and represents an optional administrative/contract policy only.

- null quota: no Construction OS application ceiling;
- configured quota: reserve space before upload and prevent only new storage-consuming writes that exceed the policy;
- existing files remain readable when a quota is reached;
- infrastructure capacity and object-store health are separately monitored in the Admin Operations Center.

## Upload lifecycle

```text
User/module requests upload
        ↓
permission + tenant check
        ↓
optional quota reservation
        ↓
private provider upload target
        ↓
client uploads bytes directly/private
        ↓
provider inspection: size + SHA-256 + detected type
        ↓
expected size/hash validation
        ↓
tenant-local deduplication
        ↓
File Asset + immutable File Version
        ↓
malware scan / media processing
        ↓
READY only after required checks
```

An upload is not trusted merely because bytes reached object storage.

## Storage accounting

Per organization track incrementally:

- committed physical bytes;
- reserved upload bytes;
- physical object count;
- revision/update time.

Logical versions may reuse one physical object when the same tenant already owns identical bytes and policy permits. Deduplication never crosses tenant boundaries.

## Tenant isolation

Tenant consistency is enforced at multiple layers:

1. backend authorization;
2. organization IDs on file records;
3. composite database foreign keys tying asset/version/storage-object relationships to the same organization;
4. private provider paths/credentials;
5. future PostgreSQL RLS defense-in-depth.

A file version or derivative from Company A must be structurally unable to point at Company B's stored object.

## File permissions

Atomic capability vocabulary begins with:

- `files.file.view`
- `files.file.download`
- `files.file.upload`
- `files.file.manage`

Owning business modules additionally enforce their own resource/project permissions. Seeing an RFI does not automatically grant download rights to every attachment unless policy permits it.

## Versioning and historical truth

A new controlled document/drawing revision creates a new immutable File Version. Existing business references may either:

- follow the asset's current version; or
- pin an explicit historical version.

Pinned references use a tenant-safe database relationship to the exact version. Older versions are never silently overwritten.

## Photos and mobile media

Original media is retained where required. UI surfaces use optimized variants rather than repeatedly serving large originals.

Typical derivatives:

- thumbnail;
- mobile preview;
- desktop preview;
- drawing/document render tiles;
- extracted metadata.

Derivatives are rebuildable and do not become the authoritative source file.

## Drawings

The File & Media Service stores drawing source/derived bytes, but the Drawings module owns construction semantics such as:

- drawing sets/sheets;
- revisions;
- overlays;
- calibration;
- measurements;
- markups;
- hyperlinks;
- RFI/photo/punch/inspection pins;
- offline drawing packages.

Large drawings should use optimized/tiled representations so mobile clients load only the required resolution/region.

## Offline support

Offline-capable modules reference managed asset/version IDs. Offline packages may cache authorized derivatives/originals according to module policy.

The Offline Sync module owns:

- encrypted device storage;
- package state;
- sync acknowledgement;
- retry/conflict semantics.

File bytes are never embedded in ordinary offline mutation JSON.

## External files

External connector URLs are not trusted permanent assets. Integration ingestion must:

1. validate source/connector;
2. fetch in isolated background processing with SSRF protections;
3. enforce size/time/type limits;
4. calculate checksum;
5. malware scan;
6. copy into private managed storage;
7. create version/source traceability;
8. link only after required validation.

Temporary vendor URLs/tokens are never stored as normal business file URLs.

## Realtime behavior

File lifecycle changes emit lightweight events such as:

- upload received;
- processing started;
- scan clean/quarantined;
- preview ready;
- file version ready;
- version created/retired.

Events contain IDs/status/revision only. Clients fetch authorized file metadata through normal APIs.

## Security processing

Release 1 file processing must support:

- actual file-type/signature validation;
- declared-vs-detected content type comparison;
- malware scanning;
- quarantine;
- size limits by policy/module;
- image/media metadata validation;
- controlled preview generation;
- no execution of uploaded active content;
- short-lived authorized downloads;
- safe filenames/content-disposition;
- audit of privileged/destructive operations.

A quarantined/failed file is not downloadable as a normal business attachment.

## Retention, legal hold and deletion

Logical deletion does not automatically destroy bytes. Deletion must consider:

- legal hold;
- business-record retention;
- other versions/assets referencing the same physical object;
- backup policy;
- audit requirements;
- integration traceability.

Physical cleanup is background/durable work, not an untracked request-time deletion.

## Performance

- large uploads go directly to private object storage rather than API process memory;
- lists are paginated;
- UI uses previews/thumbnails;
- drawing/document rendering is asynchronous;
- metadata/search extraction is asynchronous;
- storage usage is maintained incrementally;
- checksum-based lookup is indexed;
- expensive cleanup and migration are background jobs.

## Current foundation status

Implemented foundation:

- file/storage relational model;
- tenant-consistent database relationships;
- optional storage quota/accounting model;
- provider abstraction;
- direct-upload session model/service;
- expected size/checksum validation;
- tenant-local deduplication decision;
- immutable file asset/version creation;
- audit/realtime processing event integration.

Still required before Release 1 completion:

- concrete open-source/self-hosted storage adapter and local-development adapter;
- background job/outbox worker;
- malware scanner integration;
- MIME/signature detection integration;
- image/PDF/drawing derivative workers;
- authorized file/download APIs;
- upload/finalization APIs;
- retention/deletion workers;
- Admin Operations storage metrics;
- offline package integration;
- full cross-tenant/API/integration tests.
