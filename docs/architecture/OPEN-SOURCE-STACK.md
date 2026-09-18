# Construction OS Open-Source Stack Policy

## Principle

Construction OS is open-source-first for infrastructure and foundational runtime components. Paid managed services may be supported as deployment options, but the product must not require a paid proprietary service to operate.

The application must be deployable using self-hosted components under customer or Construction OS control.

## Core data platform

PostgreSQL is the primary transactional database and authoritative system of record for structured business data.

Use PostgreSQL for:

- organizations and tenants
- identity references and memberships
- roles, permissions and scopes
- projects and project controls
- workforce and field records
- accounting and finance records
- workflows and approvals
- custom-field definitions
- flexible metadata using JSONB where justified
- audit metadata
- integration mappings
- ingestion staging metadata
- notifications and operational records
- initial full-text search
- reporting projections where transactionally appropriate

PostgreSQL row-level security is used as defense in depth for tenant-owned tables where practical. Partitioning may be introduced for very large append-heavy tables such as audit, event and activity data. Replication/read replicas may be introduced when scale or availability requires them.

## What PostgreSQL should not store

Do not store large image, video, drawing, PDF or general attachment binaries directly in normal business tables.

PostgreSQL stores the metadata, ownership, checksum, security state and storage locator. Binary content lives in private object storage.

Do not use PostgreSQL as a general-purpose cache merely because it is available. Derived or disposable high-frequency cache data can move to a dedicated cache when measurements justify it.

## Object storage

Construction OS uses an internal StorageProvider interface rather than binding business modules directly to a vendor.

Supported deployment targets may include:

- local/private filesystem for development only
- SeaweedFS for lightweight self-hosted S3-compatible object storage
- Ceph Object Gateway for larger enterprise/private storage clusters
- compatible managed S3/object-storage providers when selected by the customer

Files remain private. Applications request authorized short-lived access rather than exposing permanent public object URLs.

## Cache and ephemeral coordination

A dedicated cache is optional initially.

When measurements justify it, prefer Valkey as the open-source cache/ephemeral key-value service. Valkey must never become the authoritative store for business records.

Candidate uses:

- short-lived cache entries
- rate limiting
- distributed coordination
- temporary session-related state when required by the chosen identity/session design
- job broker support where appropriate

Construction OS must remain recoverable if the cache is lost.

## Background processing

Start with PostgreSQL transactional outbox and database-backed durable jobs where practical. This reduces infrastructure during early development while preserving reliable async boundaries.

Introduce an external worker/broker stack only when concurrency, workload isolation or throughput requires it. Open-source worker frameworks may be used behind an internal job abstraction.

Heavy operations such as image processing, malware scanning, integration downloads, report generation and large imports must not block interactive API requests.

## Search

Use PostgreSQL full-text and indexed relational search first.

Introduce a separate search engine only after measured requirements exceed PostgreSQL search capabilities. Any external search index is derived data and must be rebuildable from PostgreSQL and object metadata.

## Analytics

Operational dashboards should use indexed transactional queries and maintained projections initially.

Large analytical workloads may later move to replicated/read-optimized stores. PostgreSQL remains the authoritative transactional source unless a module contract explicitly defines otherwise.

## Authentication and authorization

Do not invent cryptographic primitives or authentication protocols.

Authentication may use mature open-source identity components/libraries supporting standards such as OIDC, WebAuthn/passkeys, TOTP and secure session management.

Construction OS business authorization remains domain-specific and is enforced by the application using current tenant membership, roles, granular capabilities, data scope and system policy.

Authentication and authorization are separate concerns.

## Supporting open-source components

Expected categories include:

- PostgreSQL — transactional database
- Alembic — schema migration control
- SQLAlchemy — application data access layer
- SeaweedFS or Ceph — private object storage options
- Valkey — optional cache/ephemeral coordination
- ClamAV — upload malware scanning
- Pillow/libmagic-compatible tooling — media validation and derivatives
- open-source worker/runtime libraries — asynchronous processing as needed
- open-source reverse proxy/gateway components — TLS termination/routing depending on deployment model

Every dependency requires review for:

- license
- active maintenance
- security history
- release cadence
- deployment complexity
- portability
- backup/restore requirements
- upgrade impact
- vendor lock-in risk

## Complexity rule

Do not add infrastructure because it is fashionable or because another large SaaS uses it.

Add a component only when it solves a measured requirement that cannot be handled cleanly by the existing stack.

Preferred progression:

1. PostgreSQL + application + private file abstraction
2. add production object storage
3. add durable workers/background processing
4. add Valkey only when caching/coordination requires it
5. add separate search only when PostgreSQL search becomes insufficient
6. add analytics infrastructure only when operational reporting demands it

This keeps Construction OS lightweight while preserving a path to enterprise scale.
