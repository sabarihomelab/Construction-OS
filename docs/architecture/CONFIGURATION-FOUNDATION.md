# Company and App Configuration Foundation

Construction OS uses one common platform and common construction business engines for small contractors and large enterprises. Variation is expressed through controlled configuration, authorization and user preferences rather than separate implementations.

## Product principle

**Complex underneath. Simple on top.**

A user receives only the modules, fields, sections, actions and presentation relevant to the company, project, role and current task.

## Existing platform capabilities reused

The configuration foundation does not replace the existing platform engines. It composes them:

- Feature Registry and `OrganizationFeature` remain authoritative for module/feature availability and tenant enablement.
- Authorization remains authoritative for company/project capabilities.
- Project Membership remains authoritative for project scope.
- Metadata/Custom Fields remains authoritative for custom field definitions, options, typed values and historical field-definition versions.
- Workflow/Approval remains authoritative for workflow definitions, versions, transitions and in-flight instances.
- Notifications remains authoritative for subscriptions, channels, digests and quiet hours.
- Audit remains authoritative for immutable change history.
- File & Media remains authoritative for attachments and file versions.
- Search remains an authorized derived projection.
- Realtime Events remains the committed-change propagation mechanism.
- Offline/Sync remains authoritative for mutation idempotency, acknowledgement and conflicts.
- Reporting remains authoritative for saved views, reports, dashboards and report outputs.
- Organization/Project/User preference models remain authoritative for typed localization context such as timezone, currency and units.
- Setup/Templates remains authoritative for template identity, publication and setup runs.
- Data Governance remains authoritative for retention and legal hold.

No second implementation of these concerns may be introduced inside a business module.

## Configuration hierarchy

Effective configuration resolves in this order:

```text
Protected application definition
        ↓
Platform default
        ↓
Company override
        ↓
Project-template override
        ↓
Project override
        ↓
Membership/user presentation preference
        ↓
Effective module configuration
```

The lower layer wins only when the protected definition explicitly allows that scope.

Configuration is not copied into every project. A project may reference a published project configuration template version, and the resolver reads the template layer at runtime.

## Protected definitions

Configuration definitions are owned by application code. A tenant can change allowed values but cannot invent a new protected system key or alter its semantics.

Each registered definition declares:

- stable configuration key;
- owning module;
- value type;
- platform default;
- mutability (`protected`, `business`, or `user_preference`);
- permitted override scopes;
- historical change class;
- validation/allowed values;
- sensitivity;
- description.

Protected configuration includes security, audit, tenant ownership, IDs, revision controls, sync integrity and other platform invariants that customers must not disable.

Construction-specific modules remain opinionated. This registry is not an unrestricted low-code schema builder.

## Business configuration storage

`configuration_values` represents the stable identity of one registered setting at one scope.

`configuration_value_versions` is append-oriented and records each new value or explicit `inherit` action with:

- version;
- value;
- enabled/inherit state;
- change class;
- effective-from timestamp;
- actor;
- reason.

A future-effective version can be created without rewriting older versions.

Deleting an override means creating a disabled/inherit version. It does not delete the history.

## Configuration change classes

Every key is classified as one of:

- `presentation`
- `metadata`
- `business_rule`
- `workflow`
- `financial`
- `security`

The classification controls change review, audit risk and whether a business record must pin a configuration/rule version.

Display-only changes may safely affect presentation of historical records. Business, workflow and financial changes must not silently reinterpret finalized history.

Existing Custom Field values already pin their definition version. Existing Workflow instances already pin their workflow version. Future domain engines must preserve the relevant rule/configuration version when historical meaning depends on it.

## Project templates

The existing Setup/Templates engine remains the template lifecycle authority.

A project can reference one published `ConfigurationTemplateVersion` whose target type is `project` or `project_configuration`.

Registered configuration overrides may be stored against that template version using `project_template` scope. The project then inherits those values without copying them.

Project-specific overrides remain a separate layer and therefore survive future template publication changes unless an administrator intentionally changes the project's assigned template version.

## User preferences

Business rules never live in user preferences.

Membership preferences are organization-aware because one identity may belong to several companies. They can optionally be project-contextual.

Only definitions marked `user_preference` may be stored here, and those definitions must be presentation-class settings.

Existing specialized systems such as Saved Views and Notification Preferences continue to own their own richer preferences; the generic membership preference store is for small registered presentation settings such as compact display/favorites/default choices where a dedicated model is unnecessary.

## Localization context

The effective resolver reuses existing typed sources rather than duplicating them into generic JSON:

- organization locale/timezone/base currency/unit system/time format;
- project timezone/currency/unit system;
- user's global presentation locale/timezone/time format.

It returns both business timezone and presentation timezone so a user's display preference cannot silently change a project's business-date meaning.

## Feature configuration separation

`OrganizationFeature` is for feature enablement only.

Its historical `configuration` JSON column is preserved for backward compatibility, but new business configuration must not be written there. Existing arbitrary feature JSON is not automatically migrated because its semantics cannot safely be guessed.

When an old feature configuration is intentionally migrated, it must be mapped to registered configuration keys through an explicit migration/impact assessment.

## Effective configuration API

The API is module-scoped rather than sending all company settings with every request.

Examples:

```text
GET /api/v1/configuration/modules/core
GET /api/v1/configuration/projects/{project_id}/modules/{module_key}
```

Admin writes are separately protected:

```text
PUT /api/v1/configuration/modules/{module}/{key}
PUT /api/v1/configuration/projects/{project}/modules/{module}/{key}
PUT /api/v1/configuration/project-templates/{version}/modules/{module}/{key}
```

User preferences use a separate endpoint and cannot call the business override service.

The browser must never supply `organization_id`; tenant identity comes from the authenticated session.

## Performance and caching

The resolver loads only one requested module and the relevant hierarchy layers. It does not load configuration for unrelated modules.

Resolution queries are indexed by:

- organization;
- module;
- scope type;
- scope ID;
- effective time/version.

Two revision mechanisms support caching:

1. `OrganizationConfigurationState.revision` — a compact value in `/session/context` indicating that some business configuration changed.
2. `ConfigurationScopeRevision` — targeted per-module/per-scope revisions returned with effective configuration.

Membership preferences have their own revision.

Recommended client behavior:

```text
session context
    ↓
open module
    ↓
fetch only that module's effective configuration
    ↓
cache using organization/module/project/template/preference revisions
    ↓
configuration.changed realtime event
    ↓
invalidate only affected module/scope
```

A Foreman opening a Field page must not download Estimating, Accounting or Administration configuration.

A server-side distributed cache may be introduced later behind this revision model when measured load requires it. PostgreSQL remains authoritative; cache correctness must never depend on one application process's memory.

## Realtime behavior

A committed business-configuration change emits a small `configuration.changed` event. The event contains key/module/scope/revision metadata, not the whole company configuration.

Project-scoped changes use the existing project event authorization boundary.

A project-template assignment emits a project-scoped event causing active clients to invalidate applicable module configuration.

A membership preference change is recipient-specific.

Realtime delivery is an invalidation mechanism, not configuration truth. On reconnect, clients fetch authoritative effective configuration using revisions.

## Offline behavior

Offline packages must include only configuration relevant to the modules/projects available offline, together with their revision tokens.

Queued offline mutations preserve the base entity/configuration context needed by the owning business module. If a material business-rule configuration changes while a device is offline, the business module must validate compatibility on reconnect rather than blindly applying the mutation.

Presentation-only preference changes do not invalidate historical business meaning.

## Configuration health

Configuration health checks detect at least:

- persisted keys no longer registered by the running application;
- module/key ownership mismatches;
- tenant overrides against protected definitions;
- overrides stored at disallowed scopes.

The result feeds the existing Configuration Health/Admin Operations approach rather than creating a second health system.

## Administration experience

The future UI should use normal product language:

```text
Company Settings
  Modules
  Roles & Access
  Fields & Forms
  Workflows
  Notifications
  Templates
  Localization
  Integrations
  System Health
```

Internal concepts such as scope revision, registry, EAV, JSONB, provider contracts or outbox events are not normal admin terminology.

Sensible product defaults must make a small contractor usable without configuring hundreds of settings. Advanced settings use progressive disclosure.

## Compatibility with existing business-module work

Existing RFI and Drawing code remains frozen except for alignment changes needed by this platform foundation.

RFI and Drawings currently register a small number of configuration definitions only to prove that an existing business module can plug into the common registry:

- `rfis.default_due_days`
- `rfis.numbering.prefix`
- `drawings.allow_field_markup`

These definitions do not duplicate RFI numbering, Drawing permissions or other domain state. They are compatibility probes for the common configuration model.

## Future module requirement

Every future module must register its configurable elements before building customer-specific form logic. Standard fields/sections are product-owned; a tenant controls only the supported configuration surfaces.

A single module must support both a simple and advanced configuration without forks.
