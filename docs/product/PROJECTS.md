# Projects Module Contract

## Purpose

Projects are the primary business scope boundary inside one Construction OS organization. The module owns project identity, lifecycle metadata, project team membership and project-specific role assignment.

A project is never its own tenant. Every project remains owned by exactly one organization.

## Core objects

- `Project` — stable project identity, number, name, lifecycle state and regional/default operating attributes.
- `ProjectMembership` — connects an active organization membership to one project.
- `ProjectRoleAssignment` — assigns an organization-owned role to a project membership.

## Access model

Organization-level roles grant company-wide permissions.

Project role assignments grant the same atomic capability keys only inside the assigned project. Project permissions must never be flattened into company-wide permissions.

Examples:

```text
Company role: Employee
Project A role: Project Manager
Project B role: Viewer
Project C: no membership
```

`/api/v1/session/context` therefore returns:

- organization-wide `permissions`;
- `scopes.project` containing `*` for company-wide project access or explicit authorized project IDs;
- `project_permissions` keyed by project ID.

Search, realtime events, files, reporting, help/knowledge and future business modules must enforce both permission and project scope.

## Tenant isolation

Database relationships use organization-consistent composite foreign keys:

```text
organization
  -> project
     -> project membership
        -> project role assignment
```

A project membership cannot reference another organization's company membership. A project role assignment cannot reference another organization's role.

Tenant identity is obtained from the authenticated server session. Project create/update APIs never trust a client-supplied organization ID.

## Project lifecycle

Initial lifecycle vocabulary:

- `planning`
- `active`
- `on_hold`
- `closeout`
- `complete`
- `archived`

Lifecycle meaning may be refined by future configuration/workflow contracts. Entering closeout/complete/archived requires the higher-risk `projects.project.archive` capability in addition to normal project update access.

Projects are versioned with a monotonic `revision`. Updates require the caller's expected revision. A stale client receives a conflict rather than overwriting newer state.

## Regional and operating attributes

The project may override organization defaults where business meaning requires it:

- IANA timezone;
- currency code;
- unit system;
- structured regional address;
- start date;
- target completion date.

Changing these values does not silently reinterpret historical business records. Business modules that persist time, money or measurement meaning must retain their own applicable historical context/version.

## Capabilities

- `projects.project.view`
- `projects.project.create`
- `projects.project.update`
- `projects.project.archive`
- `projects.membership.view`
- `projects.membership.manage`

Project creation is an organization-wide administrative/business action. Other capabilities may be granted either company-wide or through project roles.

## Realtime behavior

Project creates/updates emit minimal project-scoped events after the database transaction commits through the transactional outbox model.

Project membership and project role changes increment the organization authorization revision and emit a recipient-specific `access_context.changed` event to the affected membership.

Clients refresh `/session/context` rather than trusting permission details contained in realtime payloads.

## Search

Projects expose an approved search projection containing only project identity/summary/address metadata. The projection is protected by `projects.project.view` and `scope_type=project`.

Search authorization must evaluate scoped permissions per project. A permission on Project A must not authorize a result from Project B.

## Offline behavior

Project master-data editing is not initially considered a primary offline field workflow. Project identity and allowed project list may be included in authorized offline packages as reference data.

Field/business modules operating offline reference stable project IDs and use the shared Offline Sync & Device State service.

## History and deletion

Projects are not hard-deleted by ordinary user operations. Completion/archive preserves relationships and historical references. Retention/deletion, where legally allowed, is controlled by the Data Governance module and cannot bypass legal holds or financial/contractual history rules.

Project membership and role changes are audited. Ending access removes current authorization but does not erase historical audit attribution.

## Performance expectations

- project list and project context must use tenant/project indexes and pagination once volume requires it;
- access-context calculation must not load full project records;
- realtime events carry identifiers/revisions, not full projects;
- search is a derived asynchronous projection;
- changing one project does not invalidate unrelated project client state.

## Release 1 acceptance

The Projects module is not complete merely because project CRUD exists. Release 1 requires:

1. tenant-safe persistence and migrations;
2. authenticated permission-controlled APIs;
3. project memberships and project roles;
4. project scopes in session context;
5. optimistic update protection;
6. audit and realtime access-context invalidation;
7. scope-aware Search/Realtime integration;
8. responsive UI/page contracts;
9. project setup/template integration;
10. tests for cross-tenant and cross-project access boundaries.
