# Integration Mapping and Reconciliation

## Purpose

Construction OS integrations must preserve source identity and never silently overwrite canonical business data. External records enter through staging, are transformed by versioned mapping profiles, then commit through the owning business module.

## Flow

```text
Connector
  ↓
Idempotent ingestion batch
  ↓
Staged external records + checksums
  ↓
Published mapping profile version
  ↓
Module validation / canonical command
  ↓
External ↔ internal identity mapping
  ↓
Checkpoint advancement
  ↓
Reconciliation / conflict handling
```

## Mapping profiles

Mapping profiles are tenant- and connector-scoped. A published version is historical configuration and is not edited in place. Mapping specifications cannot write the same target field more than once and later module adapters may impose stricter field/type/transformation rules.

## Checkpoints

Each connector stream has an opaque cursor and monotonically increasing revision. Advancing a checkpoint uses optimistic revision checking so competing workers cannot silently move the cursor over one another. The cursor is provider data, not business truth.

## Conflict policy

Important conflicts never use silent last-write-wins. A conflict retains source and internal values, a reason code, resolution payload, resolving user, timestamp and optional note. Domain modules determine whether source-wins, Construction-OS-wins, merge or human review is allowed.

## Traceability

External mappings retain connector, external type/id, source version/checksum, mapping version, internal type/id, reconciliation status and last reconciliation time.

## Security

Connector records store credential references rather than credential values. Staged payloads are bounded and secret-like fields are redacted. External file downloads use the File/Media ingestion path and its SSRF, type, size, malware and checksum controls rather than arbitrary URL fetching inside a mapping rule.
