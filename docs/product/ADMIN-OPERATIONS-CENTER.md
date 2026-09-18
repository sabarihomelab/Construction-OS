# Admin Operations Center

## Purpose

Provide company administrators with a simple, tenant-scoped view of system health, storage, integrations, background processing, security posture, and actionable risks without requiring infrastructure expertise.

The page must answer three questions immediately:

1. Is my Construction OS environment healthy?
2. Am I approaching any capacity, security, or operational limit?
3. Is there anything I need to act on now?

## Access

The Operations Center is visible only to users with explicit administrative permissions. Platform operators may have a separate cross-tenant operations console, but company admins must never see another tenant's operational data.

Recommended capabilities:

- `admin.operations.view`
- `admin.operations.storage.view`
- `admin.operations.security.view`
- `admin.operations.integrations.view`
- `admin.operations.jobs.view`
- `admin.operations.audit.view`
- `admin.operations.manage`

Sensitive actions require stronger permissions and may require step-up MFA.

## Page layout

### Overall Status

Show a simple state first:

- Healthy
- Attention needed
- Degraded
- Critical

Include a concise plain-language summary such as:

> Everything is operating normally. Storage usage is 41%, backups are current, and no integrations require attention.

Do not expose raw infrastructure jargon as the primary experience.

### Capacity and Storage

Show:

- total allocated storage
- used storage
- available storage
- percentage used
- growth over time
- estimated time to threshold where enough history exists
- storage by module
- storage by project
- storage by media type
- largest storage consumers
- temporary/cleanup-eligible storage
- archive usage

Warning thresholds follow the storage-capacity policy.

### Application Health

Show tenant-relevant service health, for example:

- web/API availability
- database connectivity
- file storage availability
- background job processing
- notification delivery
- search/index freshness where enabled
- AI/help service state where enabled

Company admins should see service-oriented descriptions rather than internal hostnames, IP addresses, cluster topology, credentials, or secret infrastructure details.

### Background Processing

Show:

- queued jobs
- running jobs
- failed jobs
- retries
- oldest pending job
- recent processing failures

Examples include:

- file scans
- thumbnail generation
- report generation
- imports
- exports
- integration synchronization
- notifications

### Integration Health

Per connector show:

- connected / disconnected
- last successful synchronization
- last attempted synchronization
- records processed
- warnings
- failed records
- unresolved conflicts
- credential/authorization expiry where applicable

No external-system secret or token may be shown to ordinary administrators.

### Security Posture

Show understandable indicators such as:

- MFA enforcement status
- active sessions
- suspicious/blocked login attempts
- administrators without expected MFA
- recently changed privileged access
- storage/file quarantine events
- security policy changes
- expiring certificates/credentials where tenant-managed

Do not expose exploitable low-level security diagnostics to users who do not have the required privilege.

### Backup and Recovery

Where the deployment model allows tenant visibility, show:

- last successful backup
- backup age
- restore readiness status
- last restore verification/test date
- retention summary

For managed SaaS, expose customer-relevant backup assurance rather than infrastructure-sensitive implementation details.

### Recent Operational Events

Provide a concise event timeline for meaningful operational changes:

- storage threshold reached
- integration failure
- backup problem
- service degradation
- security policy change
- unusual job backlog
- admin action affecting operations

Every item links to the appropriate detail/help context where permitted.

## AI / Help Assistant

The Operations Center includes contextual help that can explain metrics in plain language.

Examples:

- "Why is storage marked Attention needed?"
- "What happens if we reach 100%?"
- "What does oldest pending job mean?"
- "Why is the accounting connector degraded?"
- "Do I need to do anything about these failed image scans?"

Initial help must work without Internet access using product documentation, page metadata, current tenant configuration, and sanitized operational facts.

The assistant must not:

- send tenant operational data to an external model unless explicitly enabled and authorized
- expose secrets, tokens, infrastructure credentials, internal hostnames, or data from another tenant
- invent remediation steps not supported by product documentation
- execute destructive administrative actions without explicit user confirmation and authorization

## Data model guidance

Operational data should be separated from transactional business records. Suggested categories:

- `service_health_snapshots`
- `storage_usage_snapshots`
- `job_health_snapshots`
- `integration_health_snapshots`
- `security_posture_snapshots`
- `operational_events`

High-frequency telemetry should not be allowed to bloat the primary transactional path. Raw telemetry may have shorter retention, while meaningful events and audit-relevant changes are preserved according to policy.

## Performance

The Operations Center must read from summarized/projection data rather than running expensive full-database scans on every page load.

Storage totals, module usage, job counts, and health summaries should be updated incrementally or asynchronously.

## Empty states

A clean installation must not show fake statistics. Use truthful states such as:

- No storage has been used yet.
- No integrations are configured.
- No background jobs have run yet.
- No operational incidents have been recorded.

## Mobile behavior

The top status, active warnings, and required actions must remain immediately visible on mobile. Large charts/tables should collapse into concise cards with drill-down views.

## Audit

Administrative changes made from this area must be audited, including:

- retention changes
- storage policy changes
- integration changes
- retry/cancel actions
- security policy changes
- operational configuration changes

## Future platform operator console

A separate Construction OS operator console may later provide platform-wide health, tenant fleet health, infrastructure capacity, version rollout, incident management, and support diagnostics. It must remain logically and permission-wise separate from the company Admin Operations Center.
