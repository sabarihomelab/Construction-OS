# Feature / Change Impact Assessment

Use this record for every non-trivial feature, schema migration, workflow change, security change or behavior change.

## Change identity

- Change title:
- Module(s):
- Feature key:
- Release/version:
- PR/commit/migration reference:
- Date:
- Author:
- Reviewers:

## Why this change is needed

Describe the business/user problem and expected outcome.

## Current behavior

Describe what the product does before the change.

## New behavior

Describe what the product will do after the change.

## Data impact

- Existing records affected: Yes / No
- Historical meaning changes: Yes / No
- New columns/tables/objects:
- Modified columns/tables/objects:
- Deleted/deprecated data structures:
- Backfill required: Yes / No
- Existing null/missing values behavior:
- Custom-field impact:
- Tenant-isolation impact:

## Compatibility

- Old data readable by new code: Yes / No
- New data readable by previous code: Yes / No / Not required
- Existing APIs affected:
- Existing reports/exports affected:
- Existing workflows affected:
- Existing permissions affected:
- Offline/sync impact:

## Security and privacy

- Authentication impact:
- Authorization impact:
- Role/permission changes:
- Sensitive-data impact:
- File/download exposure impact:
- Audit requirements:
- Logging/redaction impact:
- MFA/step-up impact:
- Cross-tenant risk:

## Migration plan

- Migration ID/version:
- Migration type: additive / transform / backfill / destructive
- Expected duration:
- Locking/downtime risk:
- Resumable: Yes / No
- Validation after migration:
- Partial-failure detection:

## Rollback / recovery

- Application rollback possible: Yes / No
- Database rollback possible: Yes / No
- Forward-fix plan:
- Backup requirement:
- Recovery validation:

## Performance and capacity

- Query impact:
- Index changes:
- Storage growth:
- Background job impact:
- Cache/search impact:
- Expected scale considerations:

## Testing required

- Unit:
- API/integration:
- Migration/backward compatibility:
- Authorization:
- Cross-tenant isolation:
- UI/responsive:
- Workflow:
- Reporting/export:
- Security/regression:
- Performance:

## Observability / debugging

- Logs added/changed:
- Metrics added/changed:
- Correlation/audit events:
- Health checks:
- Diagnostic query/tool:
- Known failure symptoms:
- How to distinguish old vs new behavior:

## Risk assessment

- Risk: Low / Medium / High / Critical
- Probability:
- Impact:
- Main failure scenario:
- Mitigations:
- Residual risk:

## Decision

- Approved / Rejected / Needs Changes
- Approval notes:

## Post-release notes

Record discovered edge cases, customer impact, fixes, migration anomalies and lessons learned. Do not delete this section after release; it becomes part of the module's debugging history.
