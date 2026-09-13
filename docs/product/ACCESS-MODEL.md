# Construction OS Access Model

## Goal

The product UI and API must both reflect a user's current effective access. Users should see only the modules, tiles, pages, actions and data they are allowed to use.

## Access Inputs

Effective access is derived from:

1. tenant-enabled features
2. organization membership
3. assigned roles
4. project memberships/roles
5. granular capabilities
6. data scope
7. system security policy
8. current session/security state

A role is a reusable capability bundle, not the final authorization decision.

## Capability Naming

Capabilities use a stable product key such as:

- `projects.project.view`
- `projects.project.create`
- `field.daily_log.submit`
- `rfi.create`
- `finance.budget.view`
- `finance.invoice.approve`
- `payroll.compensation.view`
- `security.roles.manage`

UI labels can change without changing capability keys.

## Scope

Capabilities can be bounded by scope, for example:

- own records
- own crew
- assigned projects
- selected projects
- all company projects
- company-wide

Future tenant-defined organizational dimensions may add additional scope where needed.

## UI Rule

Permission absence should remove the related UI rather than merely disable it where practical.

Examples:

- no module permission -> module tile/navigation hidden
- no create permission -> create action hidden
- view without edit -> edit controls hidden
- no sensitive-field permission -> sensitive field omitted

The API independently enforces authorization. Hidden UI is usability, not the security boundary.

## Live Access Changes

Role and permission changes must become effective without requiring a new account or application deployment.

Expected behavior:

1. admin changes role/capability assignment
2. server persists the change and invalidates affected authorization cache/context
3. subsequent API authorization uses the new policy
4. refreshed session context returns the new capabilities
5. navigation, dashboard tiles and page actions rebuild from current access

Future real-time session notifications may refresh the UI automatically.

## Roles

Construction OS may ship default role templates, while tenants can clone or create configurable roles. Security-critical platform identities and tenant ownership controls remain system-protected.

Likely default templates include:

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

These are templates, not hard-coded application behavior.

## Person vs User

A person/worker record may exist without an application login. Authentication identity and employment/workforce identity are separate objects that may be linked.

## Audit

Changes to roles, capabilities, scopes, memberships, sensitive data access and administrative privileges must produce auditable events.
