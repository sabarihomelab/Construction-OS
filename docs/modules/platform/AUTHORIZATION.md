# Authorization Module

## Purpose

Provide capability-based access control for Construction OS without hardcoding UI behavior to role names.

The authorization model is:

`membership -> roles -> permissions -> effective capabilities`

Roles are reusable permission bundles. Permission presence means allow. Construction OS does not use conflicting allow/deny role rules in the initial model.

## Core objects

### Permission

Stable system capability identified by a key such as:

- `projects.project.view`
- `field.daily_log.create`
- `finance.budget.view`
- `finance.invoice.approve`
- `security.role.manage`

Fields:

- key
- module
- resource
- action
- description
- risk
- is_active

Permission keys are internal contracts. User-facing labels can be localized or renamed without changing the key.

### Role

Reusable permission bundle.

Fields:

- organization_id
- key
- name
- description
- is_template
- is_protected
- is_active
- version

`organization_id = null` is reserved for global role templates. Tenant-specific roles have an organization ID.

A role template is not business data and is not automatically assigned to a user. Tenant setup may later copy supported templates into a company's own role definitions.

Protected roles cannot be modified or removed through normal company-admin workflows when the platform marks them as security-critical.

### Role Permission

Associates a permission with a role.

There is intentionally no `deny` effect column. Multiple assigned roles contribute the union of allowed capabilities, bounded by tenant, project, feature and security policy.

### Membership Role

Associates an organization membership with a role.

Roles attach to membership rather than directly to the global user identity. This prevents a role granted in Company A from affecting Company B.

Project-scoped role assignment is intentionally deferred to the Project Access module so project foreign-key integrity is preserved rather than implemented through unvalidated generic IDs.

### Organization Authorization State

Each organization has a monotonically increasing authorization revision.

Fields:

- organization_id
- revision
- updated_at

Every committed change to role definitions, role permissions or role assignments must increment this revision in the same logical operation.

The revision supports live access refresh:

1. a client session receives the current authorization revision
2. an admin changes access
3. the organization authorization revision increments
4. backend requests use current database authorization immediately
5. the client detects the newer revision and refreshes session/access context
6. navigation, dashboard tiles, page actions and fields rebuild from current capabilities

The frontend revision mechanism is a usability optimization. Backend authorization remains authoritative.

## UI contract

UI visibility is permission-driven.

If a capability is absent:

- its module tile is not shown
- its navigation entry is not shown
- protected page actions are not shown
- direct route access is rejected
- backend API requests are rejected

If a capability is later granted, the corresponding UI can appear after access-context refresh without logout/login.

A user may personalize the arrangement of features they are already authorized to use, but personalization cannot expose unauthorized capabilities.

## Role templates

Construction OS will later define reviewed templates for common construction responsibilities such as:

- Company Owner
- Company Administrator
- Executive
- Project Manager
- Project Engineer / Coordinator
- Superintendent
- Foreman
- Field Worker
- Safety Manager
- Estimator / Preconstruction
- Finance Manager / Controller
- Accounts Payable
- Billing / Accounts Receivable
- Payroll Administrator
- Equipment Manager
- Auditor / Read Only
- External Collaborator

These names are defaults, not authorization logic. Code must never check `role == Project Manager` to grant access.

## Scope

This migration establishes organization-level role assignment only.

Future scopes will be modeled with real domain relationships and may include:

- assigned projects
- selected projects
- own records
- crew
- region
- division
- cost center

Project scope will be added when the Project module is rebuilt so access assignments reference valid project records.

## Security rules

- access is default-deny when no applicable permission exists
- frontend hiding is not a security boundary
- tenant membership must be active
- role must belong to the same organization as the membership, unless explicitly handled as a system template during configuration
- system templates are not directly equivalent to tenant assignment
- protected/high-risk permission changes will be audited
- critical access changes may require MFA step-up when the session/security module is implemented
- authorization cache, when introduced, must be revision-aware and disposable

## Historical behavior

Permission changes affect current security immediately and do not rewrite historical business records.

Audit history will preserve who had which role/permission and when changes were made so historical access questions can be reconstructed.

## Database migration

`apps/api/migrations/versions/20260910_0002_authorization.py`

No roles, permissions or memberships are seeded by this migration.

## Next dependent module

Feature Registry and Access Context:

- feature definitions
- tenant feature enablement
- permission-to-navigation mapping
- dashboard tile visibility
- page capability requirements
- session access-context response
- authorization revision refresh
