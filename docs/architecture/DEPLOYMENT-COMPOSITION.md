# Construction OS Deployment Composition

## Principle

Construction OS is one configurable product that can be deployed in different infrastructure shapes without changing its business-domain implementation.

The expected production model is one customer/company environment per Construction OS deployment. A deployment may run on customer-managed infrastructure, on-premises servers or cloud infrastructure. Development/demo installations may run on a developer machine.

Application-level organization/project ownership remains enforced even when a deployment currently serves one company. It is defense in depth and preserves safe authorization, imports/exports, migrations and future deployment flexibility.

## Deployment layers

Deployment composition answers where and how Construction OS runs. Company Configuration answers how the customer uses Construction OS. They are separate concerns.

```text
Deployment Composition
        ↓
Runtime Module Availability
        ↓
Protected Platform
        ↓
Company Configuration
        ↓
Project/User Effective Configuration
        ↓
Business Experience
```

## Deployment profiles

### Development

Intended for developer/demo use. Web, API, general workers and PostgreSQL may run on one machine. Local development defaults may use local storage.

### Single server

Web/API/general workers and PostgreSQL may run on one customer-managed server. File storage may be local/private or external/object storage. This profile minimizes infrastructure for a small deployment.

### Split

Web/API and worker processes can run separately from PostgreSQL and file/object storage. Heavy worker profiles can run on dedicated compute. This profile supports managed PostgreSQL, customer database servers, cloud object storage, NAS-backed providers and larger deployments.

The application must not contain business logic that depends on a particular profile.

## Database modes

Construction OS supports two deployment modes for PostgreSQL:

- `local` — installation/development tooling may install/start PostgreSQL on the application machine;
- `external` — Construction OS connects to an existing PostgreSQL endpoint and must not attempt to install or control the database service.

The application and Alembic consume the resolved `DATABASE_URL`. Business modules do not know whether the database is local, remote or managed.

A production external database should use environment-appropriate TLS, backup, availability, credential-management and network controls. Development credentials must never be promoted as production defaults.

## Storage

Business modules never bind directly to a filesystem or cloud vendor. File & Media owns the `StorageProvider` contract.

Deployment may later select adapters such as:

- local/private filesystem for development or appropriately controlled small installations;
- network/customer-managed storage through a supported adapter;
- S3-compatible object storage;
- AWS S3;
- Azure Blob/object storage;
- self-hosted object storage such as SeaweedFS or Ceph where appropriate.

PostgreSQL stores file ownership, metadata, versions, checksums and security state. Large file bytes remain outside normal business tables.

## Runtime module availability

A module being present in the release is not the same as it being active in a deployment.

```text
Code/schema capability
        ↓
Deployment available
        ↓
Company enabled
        ↓
Role/project permission
        ↓
Configuration/workflow state
        ↓
Usable
```

`RUNTIME_MODULES` selects business modules available to the running application. Required module dependencies are resolved automatically. Optional cross-module integrations do not force another module to be active.

For example, an RFI can optionally reference a Drawing when Drawings is available, but a lightweight RFI deployment must not activate the drawing-rendering workload merely because that reference type exists.

Managed installations persist an explicit module list. They do not persist `default`, because a future product release must not silently activate a newly introduced module for an existing customer.

## Schema/migration policy

All supported product schemas remain on one controlled Alembic migration history. Construction OS does not maintain different customer migration chains according to selected modules.

Reasons:

- inactive tables consume negligible runtime memory compared with application/worker processes;
- one schema history makes upgrades reproducible;
- a module can be enabled later without reconstructing an unknown database history;
- backup/restore, support and data portability remain predictable;
- relationships and historical records remain available if a module is later disabled.

Runtime/module selection controls imports, routes, search providers, scheduled/background work and UI availability. It does not create schema forks.

## Worker profiles

The normal product remains a modular monolith. Do not create one OS service/microservice per business module.

Heavy asynchronous capabilities can be assigned to worker profiles, for example:

- `general` — lightweight/common background work;
- `drawings` — drawing rendering and revision comparison;
- future `reports` — heavy report generation;
- future `documents` — OCR/document processing;
- future `ai` — optional AI workloads.

A single-server deployment may run several enabled profiles in one worker process/pool. A larger deployment may place a heavy profile on separate compute. Job handlers declare their profile/module ownership so a worker only claims work it is configured to execute.

## Module manifest

Every business module declares:

- module key;
- required module dependencies;
- optional module integrations;
- API router;
- Search provider;
- worker profiles;
- heavy-runtime flag;
- later, provider/storage/readiness requirements as necessary.

The PowerShell installer reads this same manifest through the installer CLI. Setup must not maintain an independent hardcoded business-module catalog.

This runtime manifest complements, and does not replace, the Feature Registry or Company Configuration registry.

## Windows setup lifecycle

`setup.ps1` is the operator-facing setup and maintenance entry point. It distinguishes a first installation from an existing installation.

A first installation collects or confirms:

- environment type and friendly environment name;
- deployment profile;
- local or external database mode;
- external PostgreSQL endpoint when applicable;
- browser/Web origin and API public URL;
- explicit business-module selection.

Re-running the same setup on an existing installation exposes maintenance actions such as adding modules, upgrade/refresh, reconfiguration, repair and validation. The installer lists currently installed modules and modules present in the current release but not installed.

Module addition is additive. Normal setup does not remove an existing module because historical data or cross-module relationships may depend on it. A future module-deactivation operation must run impact analysis first.

`setup-local.ps1` is the lower-level native dependency/database bootstrap used by the lifecycle installer. It supports local or external PostgreSQL, dependency installation and the common Alembic migration chain.

Installation state is recorded under `.construction-os/install-state.json`; `.env` remains the authoritative runtime configuration. Secret values are not copied into installation history.

Detailed behavior is defined in `docs/operations/INSTALLATION-LIFECYCLE.md`.

## Upgrade and backup rule

An existing installation must have a verified recovery point before migration starts.

Where compatible PostgreSQL tools are available, setup creates and verifies a custom-format `pg_dump` archive. Managed/external databases may instead provide an externally verified backup/snapshot reference. Failure to establish a backup/recovery point blocks migration.

The target version-upgrade order is:

```text
Read existing installation state
        ↓
Validate release/module manifest
        ↓
Quiesce writes
        ↓
Create + verify database recovery point
        ↓
Stage versioned application package
        ↓
Preserve environment/secrets/data
        ↓
Install dependencies
        ↓
Apply common Alembic migration chain
        ↓
Run readiness/composition validation
        ↓
Start/switch to new version
        ↓
Validate final public endpoint
        ↓
Record release/module/migration/backup history
```

The current repository implements the state-aware setup, module addition, backup gate, environment rollback copy and temporary API readiness check. Production packaging still needs versioned release-bundle staging/swap, service quiescing, final public reverse-proxy validation and signed package verification before one-click version rollback can be claimed.

Changing `DATABASE_URL` for an existing installation is treated as a database relocation/data-move operation, not a normal configuration edit.

## Cost scaling

Construction OS should support gradual infrastructure growth:

```text
Small/demo
1 application machine
+ local PostgreSQL
+ local or object storage

        ↓

Cost-efficient production
1 application server
+ managed/external PostgreSQL
+ object storage

        ↓

Growing deployment
API/web server
+ dedicated heavy worker
+ managed/external PostgreSQL
+ object storage

        ↓

Enterprise
multiple app instances as required
+ isolated worker pools by workload
+ HA/managed PostgreSQL
+ scalable object storage
```

A customer should pay for workload and resilience they actually need rather than being forced into the largest topology on day one.

## Performance/resource rule

An inactive module must not create normal runtime cost merely because its code exists in the release. When a module is not deployment-available, the application should avoid loading its business API router and Search provider. Its dedicated worker profiles should not run or claim jobs. Future frontend builds should lazy-load only visible/active product areas.

Company-level enablement can further hide an available module, but it cannot enable a module that the deployment did not make available.
