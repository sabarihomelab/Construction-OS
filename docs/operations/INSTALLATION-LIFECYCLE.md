# Construction OS Installation and Upgrade Lifecycle

## Purpose

`setup.ps1` is the operator-facing Windows setup and maintenance entry point. `setup-local.ps1` remains the lower-level dependency/database bootstrap used by the interactive installer.

The same setup entry point is intended to support the full lifecycle of one Construction OS installation:

1. first installation;
2. later module activation;
3. environment reconfiguration;
4. dependency repair;
5. version upgrade;
6. installation validation.

The installer must never treat every invocation as a clean install.

## Installation state

The installer records non-secret state in:

```text
.construction-os/install-state.json
```

The state contains the installation identifier/path, release version, environment name/type, deployment profile, masked database endpoint, runtime modules, worker profile selection, public URLs, last migration, last backup reference and a bounded action history.

`.env` remains the authoritative application runtime configuration. Secrets such as `DATABASE_URL` are not copied into `install-state.json` or the machine-wide installation pointer.

A best-effort non-secret machine pointer is stored under Windows ProgramData so future packaging can locate the installed product without searching drives.

## First installation

A first run of `setup.ps1` must collect or confirm:

- installation path;
- environment type: development, test, staging or production;
- friendly environment name;
- deployment profile;
- local or external PostgreSQL mode;
- external PostgreSQL connection when selected;
- browser/Web origin;
- public API URL;
- business modules to activate.

Module choices come from the application runtime manifest, not a hardcoded PowerShell list. Required dependencies are resolved by the same Python module resolver used by the runtime.

The installer persists an explicit `RUNTIME_MODULES` list. It must not persist `default` for a managed installation because a future release adding a new default module must not silently activate that module for an existing customer.

## Adding modules later

Re-running `setup.ps1` against an existing installation presents a maintenance menu. `Add business modules` shows:

- currently installed modules;
- modules present in the new/current release but not installed;
- module dependency resolution before configuration is changed.

The operation is additive. Normal setup does not remove/deactivate an installed business module because existing records, reports, links, exports, workflows or retention requirements may depend on it.

A future module-deactivation workflow must perform an impact analysis before changing runtime availability.

Adding a module updates the explicit runtime-module list, performs the normal backup/migration/readiness sequence, then records the successful change in installation history.

## Server and endpoint validation

Validation happens in layers.

### External database

Before migration, setup checks network reachability to the configured PostgreSQL host/port. The low-level setup then performs an authenticated database connection through Alembic/application dependencies.

### Web/API URLs

Setup validates URL syntax. Production Web origin must use HTTPS.

### Application readiness

After dependencies and migrations complete, setup launches a temporary local API instance on an unused loopback port and calls:

```text
/health/ready
```

The response must report `ready` and must include all modules the installer expected to activate. Setup records success only after this runtime validation passes.

The public/reverse-proxy URL is a separate deployment concern. Production packaging/service registration must validate the final externally reachable URL after the reverse proxy/service is running.

## Database backup before migration

For an existing installation, migration must not begin until a backup requirement is satisfied.

### Direct PostgreSQL backup

When compatible PostgreSQL client tools are installed, setup creates a custom-format `pg_dump` archive under:

```text
.construction-os/backups/database/
```

The installer verifies that the archive is non-empty and, when `pg_restore` is available, verifies that the archive catalog can be read.

### Managed/external snapshot

If database backup is performed by a managed platform or DBA instead of local `pg_dump`, the operator must supply a verified external backup/snapshot reference. The installer records the reference in installation history rather than pretending a local backup exists.

### Failure behavior

If backup creation/verification fails, migration does not start.

If a later setup step fails, the previous `.env` copy is restored. The database backup remains available for an explicit recovery procedure. The installer must not automatically overwrite a database with a backup after a failed migration because that can destroy writes made after the backup or hide the actual failure.

## Version upgrade sequence

The target production sequence is:

```text
Identify existing installation
        ↓
Read state and current runtime configuration
        ↓
Validate target release/module manifest
        ↓
Stop/quiesce application writes
        ↓
Create + verify database backup/snapshot
        ↓
Stage versioned application package
        ↓
Preserve environment/secrets/data directories
        ↓
Install dependencies
        ↓
Run common Alembic migration chain
        ↓
Run temporary readiness + migration checks
        ↓
Start new application version
        ↓
Validate final public readiness
        ↓
Record version/module/migration/backup history
```

The database migration history remains common across all module selections. Enabling a new module is not a separate customer-specific schema branch.

## Application package rollback

Database backup is implemented as the migration safety boundary. A complete production updater still needs versioned application-package staging/swap.

Before production packaging is declared complete, releases must support:

- immutable/versioned release bundles;
- installation-path discovery;
- staging a new bundle beside the active version;
- preserving `.env`, storage/data and installer state;
- service stop/start or maintenance mode;
- switching the active application version only after validation;
- retaining the previous application bundle for rollback;
- a documented forward-fix/restore policy for migrations that cannot safely downgrade.

`setup.ps1 -InstallationPath` currently rejects operating on a different release/source folder rather than copying files unsafely. This is intentional until versioned package staging/swap is implemented.

## Database relocation

Changing `DATABASE_URL` for an existing installation is not treated as a normal configuration edit. Moving from local PostgreSQL to another server/managed database requires an explicit data-move operation:

1. quiesce writes;
2. create source backup/export;
3. restore to target database;
4. validate schema/data/checksums as applicable;
5. test target connectivity/readiness;
6. switch configuration;
7. retain recovery path.

Normal setup blocks a silent database-endpoint change.

## Security rules

- Keep secrets in protected runtime configuration/secret-management mechanisms, not installation history.
- Never write database passwords to installer history or logs.
- Do not activate modules that are absent from the current runtime manifest.
- Do not silently activate modules added by a later product version.
- Do not run migration without a verified backup path on an existing installation.
- Do not auto-restore a database after a failed upgrade.
- Production endpoints require TLS and production session-cookie security.

## Future production packaging gates

Before calling the Windows installer production-ready, complete:

- versioned release package staging/swap;
- Windows service registration for API/web/workers;
- reverse-proxy/TLS setup and final public readiness check;
- supported cloud/object-storage adapters and provider validation;
- managed secret storage/service accounts;
- maintenance/write-quiesce mode;
- database restore command/runbook and restore test;
- automated upgrade test from at least the previous supported release;
- module-addition upgrade test with existing customer data;
- signed release/package verification.
