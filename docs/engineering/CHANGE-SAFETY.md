# Construction OS Change Safety Standard

## Purpose

Construction OS must evolve without corrupting, silently reinterpreting, orphaning, or exposing existing customer data. New features are backward-compatible by default. Historical records remain valid under the rules that created them unless an explicit, reviewed migration is approved.

## Core rules

1. **Historical data is immutable in meaning** — adding a feature must not silently change the interpretation of previously stored records.
2. **Additive change first** — prefer new tables, nullable columns, versioned configuration and new relationships over destructive schema changes.
3. **No destructive migration without review** — dropping columns/tables, changing data types, rewriting historical values or changing identifiers requires an approved migration and rollback plan.
4. **Tenant isolation is preserved** — migrations, background jobs, reports, exports, caches and new features must never cross organization boundaries.
5. **Feature configuration is versioned** — when workflow, metadata, validation or calculation rules change, existing records retain enough context to explain which rules applied.
6. **Read-old / write-new compatibility** — during rolling upgrades, the application should tolerate records created by the immediately previous compatible version when practical.
7. **New features cannot require old records to be backfilled unless explicitly designed and tested.**
8. **No silent fallback that changes business meaning** — missing new fields on historical records must remain distinguishable from a real entered value.
9. **Rollback must be considered before deployment** — database and application rollback paths are documented before release.
10. **Every production-affecting change is traceable** — schema version, release version and migration execution are logged.

## Data compatibility patterns

### Adding attributes

Prefer nullable/additive fields or metadata definitions. Existing records remain valid with the new attribute unset.

### Changing attribute meaning

Do not reuse an existing field for a different meaning. Introduce a new field/version and deprecate the old definition.

### Changing workflows

Store workflow/configuration version or sufficient state history so old records can still be understood and completed safely.

### Changing calculations

Do not silently recompute historical financial, payroll, cost, compliance or contractual values with new logic. Persist calculation inputs/version where required and use explicit recalculation workflows.

### Deleting configuration

Business configuration referenced by historical records should normally be deactivated, not physically deleted. Historical references must continue to resolve.

### Custom fields

Custom field definitions use stable internal IDs/keys. Renaming a label must not change the stored identity of the field. Removing a custom field from new forms must not erase historical values.

## Required impact and risk assessment

Every non-trivial feature or change must record:

- Change summary
- Affected module(s)
- Business objects affected
- Admin objects/configuration affected
- Database tables/columns/indexes affected
- API contracts affected
- UI/page contracts affected
- Permissions/roles affected
- Tenant isolation impact
- Sensitive-data/privacy impact
- Existing-data compatibility
- Historical-data interpretation impact
- Backfill required? If yes, why and how
- Migration strategy
- Rollback strategy
- Performance/capacity impact
- Reporting/export impact
- Audit impact
- Offline/synchronization impact
- Integration impact
- Security impact
- Test coverage required
- Monitoring/diagnostic signals
- Known limitations
- Risk rating: Low / Medium / High / Critical
- Reviewer/approval status

## Risk rating guidance

### Low

Additive UI/help/documentation changes with no persistence, permission or business-rule impact.

### Medium

Additive schema, new configurable fields, new API endpoints or new module behavior that does not reinterpret existing records.

### High

Changes to authorization, tenancy, money, payroll, accounting, workflow state, file access, audit, migration/backfill or existing API semantics.

### Critical

Changes that can expose cross-tenant data, alter historical financial/legal records, weaken authentication/security boundaries, delete production data or make rollback impractical.

## Migration requirements

A database migration must be:

- deterministic
- idempotent where operationally appropriate
- tenant-safe
- tested against representative old-version schemas/data
- observable through logs/metrics
- recoverable or paired with a documented forward-fix strategy
- independent of demo/sample data

Large backfills must run as resumable jobs with checkpoints rather than a single unbounded deployment transaction.

## Release gate

A change is not ready for production until:

1. impact assessment is complete;
2. compatibility behavior is documented;
3. migration and rollback behavior are documented;
4. permission/security effects are reviewed;
5. automated tests cover old and new behavior where applicable;
6. release notes identify customer-visible changes;
7. operational/debugging notes identify how to detect and diagnose failures.

## Debugging requirement

Each module maintains an internal change history containing relevant schema migrations, configuration-version changes, permission changes, known compatibility issues and diagnostic guidance. A support engineer should be able to answer:

- what changed;
- which release changed it;
- which tenants/records can be affected;
- which migration/configuration version applies;
- how to verify expected behavior;
- how to identify partial/failed migration;
- how to recover safely.
