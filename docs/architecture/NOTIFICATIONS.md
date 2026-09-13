# Notification Engine

## Purpose

Construction OS notifications must be actionable, explainable, permission-safe and configurable. The system must not become a noisy stream of duplicated alerts.

Every notification should answer:

1. What happened?
2. Why did I receive this?
3. Do I need to act?
4. What object/project does it relate to?

## Taxonomy

Release 1 uses the following top-level categories:

- `critical`
- `action_required`
- `approval`
- `assigned`
- `project_update`
- `fyi`

Categories are not a substitute for domain-specific event types. For example:

```text
rfi.assigned
rfi.overdue
submittal.review_requested
invoice.approval_requested
safety.corrective_action_assigned
```

Each notification also stores `reason_code` and plain-language `reason_text` so the UI can explain why the recipient was selected.

## Tenant and recipient isolation

Notifications belong to an organization and one organization membership, not merely a global user account.

This matters because one person may participate in multiple companies. Notification and realtime relationships use tenant-consistent composite foreign keys.

Recipient-specific realtime events also carry `recipient_membership_id`. A notification event is visible only to the matching membership even when several users share the same underlying module permission.

## Permission revalidation

A notification does not grant access to its related object.

Notifications may record:

- required permission;
- scope type/id;
- entity type/id.

When opening or listing sensitive notifications, current authorization is authoritative. If access was revoked after the notification was generated, the notification must not become a back door to the old data.

Realtime payloads include only notification identity/category hints; clients fetch permitted current data through normal APIs.

## Channels

Supported channel model:

- in-app;
- email;
- push.

Additional channels can be added later behind a provider abstraction if justified.

In-app notification persistence is authoritative for the user's notification center. Email/push are delivery channels and may fail/retry without losing the underlying notification.

## Preferences

Preferences may be set per event type and channel, with a wildcard fallback.

Delivery modes:

- immediate;
- digest;
- off.

Business/security policy may mark certain future notification types as mandatory/non-disableable; this must be explicit in the notification policy, not an accidental generic exception.

## Quiet hours

Users may configure local quiet hours.

Scheduling uses IANA timezone names and handles quiet periods that cross midnight.

Example:

```text
Quiet: 22:00–07:00 Asia/Kolkata
Email becomes due: 23:30 local
→ schedule for 07:00 local
```

A notification type may be explicitly configured to bypass quiet hours only when its domain policy justifies interruption. Category alone does not automatically bypass user preferences.

## Digests

Digest mode creates real persistent batches rather than sending many delayed individual messages.

Supported frequency model:

- hourly;
- daily;
- weekly.

A digest records:

- recipient membership;
- channel;
- frequency;
- collection window;
- scheduled send time;
- included notification IDs;
- item count;
- delivery/retry status.

Digest sending is a durable background job with an idempotency key.

## Subscriptions

Users may subscribe/unsubscribe from supported topics such as project/object/activity streams where domain policy allows it.

A subscription is tenant scoped and identifies:

- topic type;
- topic ID;
- optional event type;
- enabled state.

Being subscribed never bypasses authorization.

## Dedupe

Domain modules should provide deterministic dedupe keys for notifications that must not be duplicated by retries.

Example:

```text
rfi:<id>:assigned:<membership-id>:version:<n>
```

Dedupe identity is recipient scoped.

## Delivery pipeline

```text
Domain event/workflow action
       ↓
resolve authorized recipients
       ↓
create Notification with reason
       ↓
recipient-scoped realtime event
       ↓
load channel preference
       ↓
OFF → skip with trace
IMMEDIATE → quiet-hour scheduling → delivery job
DIGEST → add to digest batch → digest job
```

HTTP business operations do not wait for external email/push providers.

## Background jobs

Current engine job types begin with:

```text
notifications.deliver
notifications.send_digest
```

Provider failures are retried according to job/delivery policy. Permanent delivery failures remain visible in operational health.

## Templates and localization

Notifications reference stable event/template keys. Release 1 template rendering will use recipient locale/timezone and tenant configuration while preserving safe subject/preview rules.

Sensitive payroll/financial/safety details must not be placed into an email subject, push preview or other uncontrolled preview surface unless explicitly safe for that notification type.

## Workflow integration

The shared Workflow engine will generate notification events for conditions such as:

- assignment/ball-in-court;
- approval request;
- rejection;
- due soon;
- overdue/escalation;
- completion.

Reminder/escalation scheduling uses durable jobs rather than browser timers.

## Offline behavior

Notifications themselves do not substitute for offline business state.

A device that was offline catches up recipient-scoped realtime events after reconnect and refreshes the notification center. Critical business records required offline must already exist in the module's offline package/cache.

## Operational health

Admin Operations eventually shows privacy-safe summaries such as:

- queued deliveries;
- failed deliveries;
- retry rates;
- oldest pending delivery;
- provider health;
- digest backlog;
- push/email configuration state.

Ordinary admins never see provider secrets/tokens.

## Release 1 remaining implementation

The foundation currently establishes persistence, preferences, quiet-hour/digest scheduling, job integration and recipient-scoped realtime semantics.

Before Release 1 is considered complete this module also requires:

- authenticated notification-center API/UI;
- current permission/scope filtering on list/open;
- email provider abstraction and at least one deployable provider path;
- push/PWA delivery path;
- localized template renderer;
- notification policy registry including mandatory/optional channel rules;
- workflow reminder/escalation producers;
- delivery workers and retry classification;
- admin/user preference UI;
- accessibility/mobile behavior;
- operations metrics and failure remediation;
- integration/end-to-end tests.
