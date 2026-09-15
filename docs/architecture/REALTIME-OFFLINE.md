# Realtime Events and Offline Sync

## Purpose

Construction OS must feel responsive in the office and remain reliable on construction sites with weak or unavailable connectivity. Realtime delivery and offline synchronization are therefore shared platform capabilities, not optional per-page enhancements.

The core rule is:

```text
PostgreSQL committed state
        ↓
Transactional outbox event
        ↓
Realtime delivery / background consumers
        ↓
Authorized client invalidates or refreshes relevant state
```

Realtime transport is never the source of truth. A lost websocket/SSE connection must not lose business data or require a page reload to recover correctness.

## Realtime event model

Each committed event has:

- tenant/organization identity;
- monotonic sequence/cursor;
- event type and schema version;
- affected entity type/id/version;
- optional required capability;
- optional scope type/id;
- actor/session/correlation references;
- small sanitized payload;
- publish status and attempt history.

Events should normally contain identifiers, revisions and lightweight hints. Sensitive record content is fetched through the normal authorized API after the client receives the event.

### Delivery model

Release 1 may use SSE or WebSocket delivery. The transport implementation may use PostgreSQL notifications as a wake-up optimization, but durable catch-up always comes from persisted outbox/event data.

```text
Client connected
    ↓
receives event cursor 4108
    ↓
updates/invalidate relevant cached query

Connection lost
    ↓
client reconnects with last acknowledged cursor 4108
    ↓
GET changes after 4108
    ↓
server returns permitted events 4109...N
    ↓
client refreshes affected state
```

A client cursor advances across events it is not permitted to see. If access is later granted, current authoritative state is loaded through the normal access-context/API refresh rather than replaying previously hidden data.

## Authorization

Realtime delivery is tenant-scoped and permission-aware.

- required capability must currently be granted;
- scoped events default to deny unless the current access context explicitly contains that scope;
- revoking permission affects subsequent event delivery immediately;
- event payloads never bypass field/resource permissions;
- a client must refetch sensitive data through normal APIs.

## Event payload safety

Realtime payloads are deliberately small.

Current foundation limits sanitized payloads to 8 KiB and automatically redacts secret-like keys such as passwords, tokens, cookies and private keys. Binary payloads are not placed in realtime events.

Images, drawings, PDFs and other files are represented by stable identifiers and version/status events, not raw bytes.

## Offline device identity

An offline-capable client registers an installation/device context tied to:

- organization;
- current user;
- installation ID;
- platform;
- app version;
- last-seen time;
- revocation state.

Revoked devices cannot resume offline synchronization.

## Offline mutation queue

The client owns the encrypted local queue of pending operations. Every queued operation receives a client-generated mutation ID before synchronization.

Conceptual client state:

```text
LOCAL_ONLY
QUEUED
SENDING
ACKNOWLEDGED
CONFLICT
REJECTED
```

The server stores an idempotency receipt rather than the complete normal request payload. Re-sending the same mutation ID and same request produces the original result rather than creating a duplicate. Reusing the same mutation ID with different content is rejected as an idempotency conflict.

## Optimistic concurrency

Offline-capable mutable business objects use a version/revision field where concurrent editing is possible.

Example:

```text
Tablet edited entity version 6
Server currently version 8
        ↓
VERSION CONFLICT
```

The server does not silently apply last-write-wins for material business records.

## Conflict preservation

When automatic merge is not safe, Construction OS records a durable conflict containing the relevant client patch, current server values and both versions. The conflict remains open until a deterministic module rule or authorized user resolves/dismisses it.

Financial, contractual, safety and approval workflows should generally prefer explicit conflict handling over automatic overwrites.

## Server acknowledgement

A device keeps its last acknowledged realtime event sequence. Acknowledgement is forward-only: an old/stale client request cannot move the cursor backwards.

Client-local queued data is not considered safely synchronized merely because an HTTP request was sent. It is removed/archived locally only after the server returns a durable acknowledgement/result.

## Offline packages

Modules such as Drawings, Specifications, Daily Reports, Time Entry and Forms may define offline packages. Package creation/expiry is coordinated by this platform module while business modules define what data belongs in the package.

Large files are handled through File & Media storage rather than embedding bytes inside offline mutation records.

## Realtime UI behavior

The frontend uses a controlled client cache and targeted invalidation.

Example:

```text
rfi.updated
    ↓
invalidate RFI 302 + affected RFI list/count
    ↓
do not reload the entire project dashboard
```

Optimistic UI is allowed for low-risk reversible actions. High-risk accounting, payment, contractual, safety or approval actions wait for authoritative server confirmation before presenting a final state.

## Performance budgets

Initial engineering budgets for representative normal conditions are targets to be measured and refined, not contractual network guarantees:

- local UI interaction feedback: under 100 ms where no server confirmation is required;
- normal API read p95: target under 300 ms;
- ordinary save acknowledgement: target under 500 ms;
- realtime propagation after commit: target under 1 second;
- global/module search response: target under 1 second for normal queries;
- project switch useful content: target around 1 second;
- dashboard useful content: target 1–2 seconds with progressive loading;
- drawing first useful view: target around 2 seconds using optimized derivatives/tiles;
- offline local save: immediate from the user's perspective;
- reconnect/catch-up start: target under 1 second once network is available.

Every module with heavier workloads defines its own representative-data performance tests.

## Data volume and retention

Realtime/outbox data is operational data, not permanent duplicate business history. Published events are retained for a configured catch-up window and meaningful audit history remains in the Audit module.

Offline mutation receipts may be retained long enough to guarantee safe retry/idempotency and support diagnostics, then archived/expired according to governance policy.

Conflict records are retained according to the owning business record's support/audit policy.

## Failure behavior

- realtime transport unavailable: normal APIs continue to work; reconnect/catch-up restores current state;
- client offline: supported workflows continue against encrypted local state;
- duplicate retry: idempotency receipt returns the already-known result;
- conflict: preserve both sides and surface a clear resolution state;
- event consumer failure: outbox event remains durable and retryable;
- cursor too old for retained event history: client performs a scoped current-state resynchronization rather than assuming no changes occurred.

## Security

Offline local storage must be encrypted using platform-supported secure storage and scoped to the authenticated user/tenant. Logging must not include offline payload contents, session secrets or file bytes.

Device revocation, membership disablement, session/security changes and tenant access changes must prevent further protected synchronization as soon as server contact resumes.

## Release 1 definition of done

Realtime/offline support is not considered complete when tables or endpoints merely exist. Release 1 requires:

- durable event creation from committed business mutations;
- live transport (SSE/WebSocket) plus catch-up;
- authorization/scope filtering;
- client cache invalidation/reconciliation;
- encrypted offline device storage;
- mutation queue and safe retry;
- server idempotency receipts;
- version conflict detection;
- conflict resolution UI for relevant modules;
- visible sync state/errors;
- offline package support for designated field workflows;
- tests for duplicate retry, reconnect, permission revocation, cross-tenant isolation and conflicts;
- operational metrics in the Admin Operations Center.
