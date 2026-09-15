# Data Portability and Tenant Export

## Purpose

Construction OS treats customer business data as customer-owned. Authorized users must be able to export supported records, relationships and files in predictable, documented formats without relying on proprietary internal database layouts.

## Core flow

```text
Authorized export request
        ↓
Scope + sensitive-data policy check
        ↓
Durable exports.build job
        ↓
Module export providers
        ↓
Versioned manifest + records + files
        ↓
Checksums / counts / schema versions
        ↓
Private managed FileAsset
        ↓
Permission-controlled download
```

## Provider rule

Each business module owns its export contract. Export orchestration never scans arbitrary tables or serializes ORM objects blindly. A provider declares the supported entities, canonical identifiers, schema version, relationships and file references that can leave the system.

## Scope

Release 1 supports company, project and module-scoped export requests. Audit history is separately permission-controlled because it can contain security-sensitive operational context.

## Manifest

Every generated package has a stable manifest version. Manifest items record module, entity type, relative path, schema version, record count, file count and optional SHA-256 checksum. Paths are validated against traversal.

## Files

Export output is itself a managed private file asset. Existing attachment permissions and legal/retention rules still apply while the export is being assembled. Large packages are produced asynchronously.

## Historical compatibility

Export schemas are versioned. A future export-schema change must either preserve compatibility or increment the relevant contract version and provide a documented migration/compatibility window.

## Security

- no raw database dump endpoint;
- no cross-tenant export;
- no permanent public download URL;
- sensitive categories require their own permissions;
- export creation and download are auditable;
- temporary output follows retention/cleanup policy;
- export jobs must not persist secrets in job payloads or manifests.
