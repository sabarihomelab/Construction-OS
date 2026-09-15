# Background Jobs and Worker Engine

## Purpose

Construction OS uses durable background jobs for work that is too heavy, slow, failure-prone, or externally dependent to run inside a normal HTTP request.

Examples include:

- file malware scanning and type detection;
- drawing page/sheet extraction and rendering derivatives;
- drawing tile generation;
- estimate recalculation at large scope;
- report generation;
- imports and exports;
- search indexing;
- notification delivery;
- external synchronization;
- AI extraction/summarization where enabled;
- closeout package generation;
- large analytics/projection rebuilds.

A web request may enqueue work, but the browser must not have to remain connected for that work to complete.

## Core model

```text
Business transaction
      ↓
BackgroundJob persisted
      ↓
HTTP request returns quickly
      ↓
Worker claims job with lease
      ↓
Handler performs bounded work
      ↓
heartbeat / progress
      ↓
success OR retry OR terminal failure
      ↓
realtime event / notification / projection update as appropriate
```

PostgreSQL is the durable queue source of truth in the initial architecture. A future queue/broker may be introduced for scale, but must not remove durable job state, idempotency, attempt history or tenant ownership.

## Job identity

Each job records at minimum:

- organization/tenant;
- stable job type;
- payload schema version;
- optional idempotency key;
- status;
- priority;
- availability/schedule time;
- attempt count and maximum attempts;
- worker lease owner/expiry;
- heartbeat;
- progress;
- result summary;
- last error;
- cancellation state;
- actor/correlation context.

Job payloads contain small instructions and stable identifiers, not large files or complete business datasets.

For example:

```json
{
  "file_version_id": "...",
  "drawing_sheet_id": "..."
}
```

not raw PDF/image bytes.

## Idempotency

Long-running workflows must be safe to retry.

The queue supports an optional tenant + job type + idempotency key uniqueness boundary. Business modules should use deterministic idempotency keys for operations where duplicate execution would be harmful.

Example:

```text
files.process_version
file-version:<id>:process:v1
```

Repeated enqueue attempts return/use the existing logical job rather than scheduling duplicate work.

Idempotency at the queue level does not replace idempotency inside external integrations or financial posting rules.

## Worker leases

Workers claim jobs using database row locking with `SKIP LOCKED` semantics.

A running job has:

- `lease_owner`;
- `lease_expires_at`;
- `heartbeat_at`.

The worker periodically extends the lease. If the worker process or machine disappears, the lease eventually expires and a recovery process marks the attempt abandoned and either retries or terminally fails the job according to its attempt policy.

A worker crash must not leave a job permanently stuck in `running`.

## Attempt history

Each execution attempt has its own record with:

- attempt number;
- worker identity;
- start/end timestamps;
- heartbeat;
- progress;
- status;
- error code/message;
- bounded metrics;
- processed item count.

Old attempts are retained according to operational/audit retention policy so support can explain repeated failures without inspecting customer payload content.

## Progress

Handlers may publish bounded progress such as:

```text
42% — Rendering sheet 84 of 200
```

Progress is informative, not transactional truth. Business completion remains determined by the authoritative module state and successful job completion.

Progress updates may feed the Admin Operations Center and realtime UI.

## Cancellation

Queued/retrying jobs may be cancelled immediately after authorization.

Running jobs receive a cancellation request. Cooperative handlers should check cancellation at safe checkpoints. Destructive or financially authoritative operations may define points after which cancellation is prohibited and a compensating/forward-fix workflow is required.

Cancellation actions are audited.

## Retry policy

Retry is appropriate for transient failures such as:

- temporary object-storage outage;
- short external-service outage;
- network timeout;
- worker interruption;
- transient database/dependency failure.

Retry is not appropriate for deterministic validation failures unless input/configuration changes.

Handlers classify errors into retryable/non-retryable outcomes. Retry delays may later use exponential backoff/jitter. Maximum attempts are explicit per job.

## Payload safety

Current foundation bounds sanitized job payloads to 32 KiB and result summaries to 16 KiB.

Secret-like fields are redacted and binary content is omitted. Large source data remains in its authoritative table/object storage and is referenced by ID.

Jobs must never become an alternate secret store.

## Tenant isolation

Every customer/business job belongs to one organization.

Attempt records have tenant-consistent composite foreign keys back to their job. Admin job inspection must always be tenant-scoped unless using the separate internal platform-operator console.

## Handler registry

Business/platform modules register handlers by stable type, for example:

```text
files.process_version
 drawings.render_sheet
 drawings.build_tile_pyramid
 estimate.recalculate
 reports.generate
 search.index_entity
 integrations.sync_connector
 closeout.build_package
```

Business code depends on the Construction OS job interface, not Celery, RabbitMQ, Redis, Kafka or another vendor-specific API.

This preserves the ability to change the transport/execution implementation later without rewriting domain modules.

## Transactions

Enqueueing related background work should occur in the same database transaction as the state change that requires it whenever possible.

Example:

```text
FileVersion persisted
+ files.process_version job persisted
+ audit/event records persisted
COMMIT
```

This avoids the failure mode where the business record commits but required background processing is forgotten.

Handlers should avoid keeping one database transaction open for the entire duration of very long work. They should process in safe checkpoints and persist progress/state appropriately.

## Realtime relationship

Jobs and realtime events solve different problems:

- jobs perform durable asynchronous work;
- realtime events tell authorized clients what changed.

Example:

```text
Drawing uploaded
→ render job queued
→ worker renders derivatives
→ DB state updated
→ drawing.processing.completed event
→ connected UI refreshes sheet
```

Realtime delivery failure never causes the job result to be lost.

## Operational health

Admin Operations should eventually summarize:

- queued/running/retrying/failed counts;
- oldest pending job;
- failure rate by job type;
- average/p95 processing duration;
- repeated failures;
- abandoned worker leases;
- retry volume;
- queue age;
- worker availability;
- tenant resource consumption.

Capabilities:

- `admin.operations.jobs.view`
- `admin.operations.jobs.manage`

Sensitive retry/cancel operations require explicit authorization and audit; high-risk actions may require step-up MFA.

## Release 1 engine consumers

The Release 1 job engine is a dependency for at least:

- File & Media;
- Drawings;
- Estimating/Takeoff;
- Search;
- Notifications;
- Reporting;
- Integrations/Ingestion;
- Data Portability/Export;
- Closeout;
- AI processing where enabled;
- Admin Operations projections.

Each consuming module documents its job types, idempotency rules, retry classification, cancellation behavior, progress semantics and recovery strategy in its module contract.
