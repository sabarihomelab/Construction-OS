# Construction OS Object Model

## Purpose

Construction OS uses three object classes so the platform can stay configurable without allowing customer configuration to weaken security or data integrity.

## 1. System Objects

System objects are controlled by the product and are not customer-removable. They support identity, tenancy, security, auditing, integrity, versioning and platform operation.

Examples:
- user identity
- organization ownership
- record identifiers
- created/updated metadata
- audit metadata
- security/session state
- internal record version

System objects are never exposed as freely editable custom fields.

## 2. Admin Objects

Admin objects define how a customer wants Construction OS to behave. They are tenant-scoped configuration rather than construction transaction data.

Examples:
- roles
- permissions
- custom fields
- lookup values
- workflow definitions
- approval rules
- numbering rules
- page configuration
- feature/module configuration
- notification rules

Admin objects may be configurable only within product-defined safety and integrity rules.

## 3. Business Objects

Business objects represent actual construction and accounting activity.

Examples:
- project
- person/worker
- crew
- daily log
- time entry
- RFI
- submittal
- drawing
- inspection
- incident
- equipment item
- material transaction
- estimate
- budget
- commitment
- change order
- invoice
- payment
- payroll batch
- journal entry

## Custom Attributes

Business objects may expose customer-defined attributes through the metadata engine. A custom attribute definition should contain at minimum:

- object type
- field key
- label
- description/help text
- data type
- required flag
- default value where allowed
- validation rules
- selectable values where applicable
- visibility rules
- editability rules
- search/filter/report behavior
- display order
- active/inactive state

Custom attributes must never replace product-owned security, tenant, audit or relationship fields.

## Design Rule

Before implementing any business object, document:

1. purpose
2. core system attributes
3. product-required attributes
4. customer-configurable attributes
5. relationships
6. validation
7. lifecycle/statuses
8. workflow
9. permissions
10. audit events
11. page usage
12. help content
13. reporting/search requirements
