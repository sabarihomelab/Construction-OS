# Metadata and Custom Fields

## Purpose

The Metadata module lets a company extend supported Construction OS business objects without changing the core database schema for every customer-specific attribute.

The design is intentionally hybrid:

- core business fields remain relational and strongly typed
- administrator-defined attributes use versioned metadata
- custom values use typed PostgreSQL columns where practical
- JSONB is reserved for configuration and genuinely complex/multi-value data

This avoids both extremes: hardcoding every customer field and turning the whole product into an untyped EAV database.

## Stable identity

A custom field is identified by:

- organization
- entity type
- stable field key

After creation, `entity_type`, `key`, and `field_type` are immutable through the normal update contract.

If the business meaning or type must materially change, the existing definition is retired and a new definition is created. Stable keys are not repurposed to mean something different.

Display properties such as label, description, help/configuration, required state, visibility, reporting flags, and permissions can evolve through versioned revisions.

## Supported field types

Current foundation types:

- text
- long text
- integer
- decimal
- currency
- boolean
- date
- timezone-aware datetime
- single select
- multi select
- user reference
- company reference
- project reference
- phone
- email
- URL
- attachment reference
- measurement

Additional types require impact assessment before extending the stable type vocabulary.

## Definitions

`custom_field_definitions` contains current configuration including:

- entity type
- stable key
- label and description
- immutable field type
- required/default behavior
- validation rules
- type-specific configuration
- searchable/filterable/reportable flags
- visible/editable flags
- optional view/edit permission keys
- display order
- active state
- current version

Definitions are tenant-scoped.

## Definition history

Every definition version is snapshotted into `custom_field_definition_revisions`.

The snapshot includes the definition and its options at that version. Historical custom values store `definition_version`, allowing later debugging to determine which metadata definition was current when the value was written.

Configuration changes use optimistic concurrency through `expected_version`. If another administrator changed the field first, the stale update is rejected instead of silently overwriting the newer configuration.

## Select options

Options use stable internal keys and mutable display labels.

Removing an option from future use should deactivate it rather than delete its historical identity. Existing records may therefore continue to explain an old option even when that option is unavailable for new data.

## Typed value storage

`custom_field_values` does not contain one generic text `value` column.

It provides typed storage for:

- text
- numeric (`NUMERIC(30,10)`)
- boolean
- date
- timezone-aware datetime
- UUID/reference
- JSONB for complex/multi-value cases
- currency code
- unit code

Only the relevant columns are populated for a field type.

This allows indexes/reporting/filtering to use native PostgreSQL types rather than parsing localized strings at query time.

## Canonical values

Presentation formatting never becomes database truth.

Examples:

- currency: decimal amount + upper-case three-letter currency code
- measurement: decimal value + explicit unit identity
- date: date only, never converted through UTC
- datetime: timezone-aware instant required
- references: UUIDs
- email: normalized text
- select values: stable option keys, not labels

Values such as `10 ft`, `$1,200`, or locale-formatted numbers are presentation/input concerns and are normalized before persistence.

## Defaults

Default values are validated against the immutable field type and stored in a canonical JSON representation. A later display-locale change does not reinterpret the default.

## Permissions

Custom definitions can optionally require permission keys for viewing or editing the field.

Initial administration permissions:

- `admin.custom_field.view`
- `admin.custom_field.manage`

The planned Administration > Custom Fields page remains hidden until the UI and authenticated administration APIs are implemented.

Field-level permissions are additional restrictions. They never grant access to a business object the user otherwise cannot access.

## Business-object validation

A custom value stores the owning `entity_id`, but the generic metadata table does not create a polymorphic foreign key to every possible business table.

The owning module is responsible for validating:

- the entity exists
- the entity belongs to the same tenant
- the definition applies to that entity type
- the caller has object-level and field-level authorization

This prevents the Metadata module from bypassing tenant/business authorization.

## Historical behavior

Changing a definition affects future editing/validation according to the new version. It does not rewrite historical custom values.

Examples:

- renaming a label changes presentation but preserves field identity
- deactivating a select option prevents new selection but preserves historical option identity
- making a field required does not make old records invalid merely because they predate that requirement
- retiring a field does not delete old values

Explicit historical migration, when genuinely required, must use an assessed migration workflow and audit the affected records.

## Audit

Definition creation/change and option creation already emit compact audit events with before/after definition snapshots.

Audit sanitization still applies, so metadata configuration cannot be used to leak credentials or large binary payloads into audit storage.

Custom business-value changes will normally be audited by the owning business module as part of the business transaction, avoiding duplicate audit events disconnected from the business action.

## Performance

The design avoids a naive string-only EAV model.

Performance principles:

- native typed columns for commonly queried values
- tenant + definition + entity uniqueness
- tenant/entity indexes for object retrieval
- definitions/options loaded and cached later when justified
- no per-row schema changes for tenant fields
- no full JSON document rewrite for every core business record

Additional indexes for searchable/filterable custom fields should be introduced from measured query patterns rather than indexing every possible value column by default.

## Current status

Implemented foundation:

- versioned definitions
- stable field/option keys
- definition revision snapshots
- optimistic update versioning
- typed value normalization and storage
- canonical currency/measurement/date/datetime/reference handling
- select option validation
- field-level permission references
- administration permission vocabulary
- planned feature-registry entry
- metadata audit integration
- migration and invariant tests

Not yet exposed as tenant administration APIs or UI. Those surfaces will be added only after authorization/write-policy helpers are in place.
