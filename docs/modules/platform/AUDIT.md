# Audit

## Purpose

The Audit module records durable, tenant-scoped evidence of meaningful business, security, configuration, and administrative changes.

Audit is not a debug log and is not a copy of every record. It stores compact events that answer who changed what, when, through which session/context, and what meaningful values changed.

## Storage principles

Audit must remain useful without becoming a storage bottleneck.

Rules:

- do not record every read/API request as an audit event
- do not copy uploaded files or binary data into audit
- do not store passwords, tokens, cookies, API keys, recovery codes, or private keys
- avoid full record snapshots when a compact field-level change is enough
- truncate oversized strings and collections
- use stable event/action names
- keep audit writes in the same database transaction as the change when possible

Operational logs and telemetry belong to the Observability module and may have different retention.

## Event shape

`audit_events` contains:

- event ID
- organization ID
- occurrence timestamp
- actor type
- optional actor user ID
- optional session ID
- action
- target type
- optional target ID
- optional correlation ID
- risk classification
- optional reason
- sanitized change payload
- sanitized metadata
- audit schema version

The table intentionally has no `updated_at` field. Audit events are append-oriented and should not be edited through ordinary application workflows.

## Actor types

- `user`
- `system`
- `integration`
- `support`

Support actions must eventually require explicitly approved/time-bounded support access and must be clearly distinguishable from customer-user actions.

## Risk

- `low`
- `medium`
- `high`
- `critical`

Examples of high/critical audit events include security-role changes, financial access changes, tenant-isolation policy changes, MFA/security resets, and destructive data operations.

## Sanitization

Audit payload sanitization automatically redacts keys associated with:

- passwords
- tokens
- secrets
- cookies
- authorization headers
- API keys
- private keys
- recovery codes
- file contents
- base64/binary/blob payloads

Binary values are omitted. Strings, lists, and nesting depth are bounded to prevent accidental audit amplification.

Module-specific audit emitters remain responsible for sending only useful, minimal data.

## Feature/configuration changes

The Feature Registry is already connected to Audit. A tenant feature change records:

- feature key
- prior effective/stored state
- new state
- feature configuration version
- release state
- actor/session/correlation context when supplied
- feature-derived risk classification

Omitted configuration preserves existing configuration rather than clearing it.

## Transaction rule

For business/configuration changes, the preferred pattern is:

1. validate authorization and input
2. modify domain state
3. create audit event in the same database transaction
4. commit once

If the business change fails, its audit claim should not remain as though the change succeeded.

Security monitoring events that describe failed attempts may use a separate security-event path later because they need to persist even when no business transaction commits.

## Query and scale

Primary query paths are indexed for:

- organization + time
- target
- action
- actor
- correlation ID

Audit will remain in PostgreSQL initially. When volume justifies it, time-based partitioning/archive can be introduced through an assessed migration without changing the logical event contract.

## Retention

Retention policy will be configurable by deployment/company policy within compliance constraints. Retention must not be implemented as uncontrolled user deletion.

Future archival/deletion jobs must be authorized, auditable, tenant-scoped, and compatible with legal hold requirements where applicable.

## Historical compatibility

Audit action names and schema versions are historical contracts.

An existing action name must not later be reused to mean a materially different event. Payload evolution uses `schema_version` where interpretation changes.

## Current status

Implemented foundation:

- append-oriented audit schema
- compact JSONB changes/metadata
- actor/session/correlation context
- risk classification
- secret/binary redaction
- payload limits
- feature configuration audit integration
- safety tests

Next integrations will include role/permission administration, metadata configuration, integrations, and high-risk administrative changes as those write services are implemented.
