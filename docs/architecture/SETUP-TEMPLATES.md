# Setup, Templates and Configuration Health

## Purpose

Construction OS must be deployable without requiring a consultant to manually configure every company and project. Guided setup is therefore a platform capability, but ease of setup must not bypass module validation, permissions, audit, or historical-safety rules.

## Core rule

```text
Template definition
    ↓
Versioned template payload
    ↓
Module-owned validation
    ↓
Setup run / dry-run result
    ↓
Durable background apply job
    ↓
Module-owned transaction
    ↓
Audit + realtime refresh
```

A template is not an arbitrary database patch. Each target module registers a provider that owns validation and application of the configuration it understands.

## Release 1 use cases

- company setup;
- project templates;
- role/access templates;
- workflow templates;
- cost-code/financial structure templates;
- field/daily-log defaults;
- notification defaults;
- reusable configuration packages;
- import-assisted onboarding;
- configuration health diagnostics.

## Historical behavior

Template versions are immutable once published. A new template version affects future setup/application unless a module explicitly supports a controlled migration. Existing business records are never silently reinterpreted simply because an administrator edits a template.

## Configuration health

Modules can publish tenant-scoped health checks such as missing cost-code mappings, incomplete workflow configuration, invalid notification settings, unavailable storage provider, or project configuration gaps. Results are designed to feed the Admin Operations Center and plain-language help assistant.

## Security

Viewing and applying setup are separate permissions. High-impact configuration application is auditable and can later require step-up MFA or workflow approval depending on the affected domain.
