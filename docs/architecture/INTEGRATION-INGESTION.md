# External Data and File Ingestion

Construction OS treats every external source as untrusted input. Connectors may read data from external applications, but they never write directly to canonical business tables or private object storage records.

## Inbound data flow

```text
External Provider
      ↓
Integration Gateway
      ↓
Source Authentication / Rate Limits
      ↓
Raw Ingestion Record
      ↓
Validation
      ↓
Staging
      ↓
Mapping / Transformation
      ↓
Duplicate and Conflict Check
      ↓
Business Validation
      ↓
Commit Transaction
      ↓
Canonical Construction OS Object
      ↓
Audit + Sync Checkpoint + Reconciliation State
```

Every imported record keeps source traceability including tenant, connector, external object type, external identifier, source version/etag where available, ingestion time, mapping version and reconciliation status.

## Idempotency

Repeated delivery of the same external event or record must not create duplicate business objects. Connector operations require stable external identities and idempotency keys/checkpoints where the source supports them.

## Historical safety

A source change does not silently overwrite historical Construction OS meaning. Update rules are explicit per object and field. Significant changes retain enough source/version information to explain why a value changed.

## Conflicts

Conflicts must be explicit. Supported outcomes can include:

- external source wins for explicitly source-owned fields;
- Construction OS wins for internally owned fields;
- merge according to a documented rule;
- hold for human review;
- reject/quarantine.

No connector may use a hidden last-write-wins rule for financially, contractually or operationally significant data.

## External files and images

External file URLs are references, not trusted permanent assets.

Preferred flow:

```text
External file reference
      ↓
Validate connector + allowed source
      ↓
Isolated background fetch
      ↓
Enforce size/time limits
      ↓
Detect actual file type
      ↓
Malware/security scan
      ↓
Checksum
      ↓
Private object storage
      ↓
Attachment record
      ↓
Preview/thumbnail processing
      ↓
READY / QUARANTINED / FAILED
      ↓
Link to canonical business object
```

The application should not permanently embed vendor-signed URLs, access tokens or externally hosted temporary image links in business data.

## External asset metadata

An imported attachment can retain:

```text
id
organization_id
business_object_type
business_object_id
storage_key
original_filename
content_type
byte_size
sha256
source_connector_id
source_external_id
source_external_version
source_reference
uploaded/imported_at
scan_status
processing_status
version
```

Sensitive credentials or temporary signed URLs must never be persisted as ordinary metadata.

## File versioning

If an external drawing/image/document changes, the default behavior is to create a new managed file version rather than mutating the previously imported bytes in place. Historical references remain explainable.

## SSRF and remote-fetch protection

Remote ingestion workers must not fetch arbitrary user-controlled URLs. Connector-specific allowlists and outbound-network policy should be used. Requests to loopback, private/internal infrastructure, cloud metadata endpoints and other prohibited destinations must be blocked. Redirect destinations must be revalidated.

## Performance

Large downloads, image transforms, malware scans and synchronization run as durable background jobs rather than blocking API requests. The web/API tier coordinates work and returns progress/state.

## Tenant isolation

Tenant context must be preserved at every ingestion stage: raw/staged records, jobs, files, mapping rules, reconciliation records, logs and search/index updates. No external connector credential can authorize access to another Construction OS tenant.

## Failure handling

Failures are never silently discarded. Ingestion records move through explicit states such as:

```text
RECEIVED
VALIDATING
STAGED
PROCESSING
READY_TO_COMMIT
COMMITTED
QUARANTINED
RETRYING
FAILED
```

Diagnostics must be sufficient for support/debugging without logging secrets or unnecessarily exposing customer payloads.
