# Feature Registry and Access Context

## Purpose

The Feature Registry is the canonical Construction OS catalog used to compose navigation, pages, tiles, and actions from released product capabilities, tenant configuration, and effective permissions.

The registry is product-owned and version-controlled. Tenant configuration may enable or disable only features explicitly marked as tenant-configurable; it cannot redefine a feature key, route, permission requirement, release state, sensitivity, or parent relationship.

## Core rule

A feature is visible only when all applicable conditions are true:

1. the feature release state allows use;
2. the feature is enabled by product/default and tenant configuration;
3. the user has every required permission;
4. any parent feature is also visible.

Frontend visibility is user experience only. Backend authorization remains mandatory for every protected request.

## Release states

- `available`: usable in normal production contexts
- `preview`: available only when an explicitly permitted preview context is used
- `planned`: defined for product planning but never exposed at runtime
- `retired`: no longer available

A tenant override cannot promote a planned or retired feature to production availability.

## Product-owned registry

Canonical feature definitions live in application code rather than tenant database rows. Each feature may define:

- stable key
- display name
- feature kind
- parent feature
- route
- required permissions
- tenant configurability
- default enabled state
- release state
- sensitivity classification
- display order
- mobile support
- offline support
- help topic

Stable keys must not be repurposed to mean a different capability in a later release.

## Tenant feature state

PostgreSQL stores only tenant-specific feature overrides and configuration in `organization_features`.

Key fields:

- `organization_id`
- `feature_key`
- `enabled`
- `configuration`
- `version`
- `updated_by_user_id`

Absence of a row means the product default applies.

Configuration changes increment the row version. Feature changes also increment the organization's authorization revision so clients can refresh their access context.

## Protected platform features

Core recovery/administration surfaces such as Home, Administration, Roles & Access, Operations Center, and Help are not tenant-disableable through normal feature flags. Their visibility may still depend on permissions.

This prevents a company administrator from accidentally disabling the controls required to administer or recover the tenant.

## Access context

The access-context service resolves an active organization membership into:

- organization ID
- membership ID
- current authorization revision
- effective permission keys
- currently visible feature definitions

System role templates are not intended to be assigned directly. Runtime role resolution accepts active tenant roles belonging to the same organization as the membership.

## Permission catalog

Permission definitions are system configuration data, not tenant business data. The initial catalog is seeded by migration and mirrored by the version-controlled permission catalog.

Feature-required permissions must exist in the permission catalog. Tests enforce this invariant.

## UI composition

The frontend will eventually consume the authenticated session/access context and construct:

- navigation groups
- dashboard tiles
- routes
- page actions
- field/control visibility

A missing feature or permission is omitted rather than rendered as an unusable control unless a specific product experience requires explaining unavailable functionality.

## Historical compatibility

Adding a new feature does not modify historical business records.

Changing a feature definition requires impact assessment when it can affect:

- existing routes or bookmarks
- permissions
- tenant configuration
- stored feature configuration
- reporting
- integrations
- offline behavior
- audit interpretation

Stable feature keys must not be reused after retirement.

## Security considerations

- tenant feature flags never grant permissions
- permissions never override product release state
- feature visibility never substitutes for backend authorization
- feature keys supplied by clients must be validated against the product registry
- non-configurable features reject tenant override writes
- configuration changes require authorization and will be audited by the Audit module

## Current status

Implemented foundation:

- product-owned feature registry
- release-state filtering
- permission filtering
- parent-feature filtering
- tenant override storage
- authorization revision integration
- access-context composition service
- initial permission catalog
- schema/invariant tests

Not yet exposed as public API. Authenticated session endpoints will be introduced by the Session/Security module.
