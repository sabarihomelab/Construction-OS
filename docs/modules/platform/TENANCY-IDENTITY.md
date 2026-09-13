# Tenancy and Identity Module

## Purpose

Provide the stable company and user identity boundary that every Construction OS module depends on.

This module answers:

- which organization owns the request and data
- which application identity is authenticated
- which organizations that identity belongs to
- whether that membership is active
- which organization and user preferences apply

Authorization roles, permissions, project scopes, sessions, MFA and feature visibility are separate platform modules built on top of this foundation.

## Core objects

### Organization

Stable company identity.

Core fields:

- id
- name
- legal_name
- slug
- country_code
- is_active
- created_at
- updated_at

Mutable operating preferences do not belong directly on the organization identity record.

### Organization Settings

One-to-one configuration record for an organization.

Initial fields:

- organization_id
- locale
- timezone
- base_currency
- unit_system
- time_format
- first_day_of_week
- settings_version
- storage_quota_bytes

`settings_version` is available for version-aware configuration changes. Historical business records must preserve additional snapshots or effective configuration references when their meaning depends on settings.

`storage_quota_bytes` uses a 64-bit integer so multi-terabyte deployments are supported. A null value means capacity is controlled by a higher-level deployment/platform policy rather than an unlimited promise.

### User

Application identity independent of any one company.

Core fields:

- id
- primary_email
- display_name
- identity_provider
- identity_subject
- status
- is_active
- last_authenticated_at
- created_at
- updated_at

A user may belong to more than one organization. The external identity provider subject is provider-agnostic so a standards-based identity service can be introduced without changing business records.

### User Preferences

Presentation preferences belonging to the user rather than the company.

Initial fields:

- locale
- timezone
- time_format
- date_format
- number_format

A user preference may override presentation defaults but must not override security, accounting, compliance or historical business meaning.

### Organization Membership

Joins a user identity to an organization.

A user can have at most one membership record per organization. Membership lifecycle is explicit:

- invited
- active
- suspended
- ended

Membership kinds are:

- internal
- external
- service

Roles and permissions attach to memberships in the Authorization module rather than directly to users.

## Data rules

- no sample organization or user is seeded
- company preferences are separate from stable tenant identity
- user identity is separate from workforce/employee records
- a worker may exist without an application login
- a login may have memberships in multiple companies
- email uniqueness is case-insensitive
- organization membership is unique by organization and user
- organization-owned data must eventually reference the organization with foreign keys and tenant enforcement
- mutable settings must not silently reinterpret historical records

## Security boundaries

This module does not expose public CRUD endpoints by itself.

The previous scaffold organization/project/workforce/field routes are not wired into the application while authentication and authorization are being rebuilt. Future routes must require an authenticated tenant context except for a narrowly controlled first-run/bootstrap flow.

Backend authorization remains authoritative even when frontend navigation is permission-driven.

## Database migration

Baseline migration:

`apps/api/migrations/versions/20260910_0001_platform_identity.py`

It creates only platform tenancy/identity tables and no business data.

## Compatibility and change risk

Changes to this module are high impact because most modules will depend on organization and user identifiers.

Any future change to:

- organization identity semantics
- membership identity
- email uniqueness
- identity-provider mapping
- tenant ownership
- deletion behavior
- organization settings version behavior

requires an impact assessment and migration/rollback plan.

## Next dependent module

Authorization and access context:

- roles
- permissions/capabilities
- role permissions
- membership role assignments
- project-scoped assignments
- feature visibility
- effective access calculation
- live permission refresh contract
