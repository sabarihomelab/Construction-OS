# Workforce & Time

## Purpose

Workforce & Time is the shared construction labor foundation for worker identity, crews, project staffing and approved project time. It is one configurable module used by both small contractors and larger enterprises.

It does not make an application login the same object as a Worker, and it does not embed country-specific payroll or statutory tax logic into time capture.

## Object model

```text
Company
├── Worker
│   └── optional linked Organization Membership / login
├── Crew
│   └── dated Crew Membership history
└── Project
    └── Project Worker Assignment
        └── Weekly Timecard
            ├── Time Entries
            ├── shared Workflow instance when approval is enabled
            └── append-oriented history
```

A Worker can exist without a Construction OS login. This is required for subcontract labor, field workers who do not use the application directly, imported workforce records and future payroll/integration scenarios.

## Protected identity versus configurable presentation

Stable record IDs, tenant ownership, project relationships, revisions, workflow identity and historical references are protected platform data and cannot be deleted by company configuration.

Protected or standard attributes may still be hidden from normal user experiences when configuration permits. Hiding a field is not the same as deleting its stored identity.

Worker business attributes are exposed through the common Configuration and Metadata engines. Company administrators can control supported standard-field presentation and business requirements, while company-specific attributes use the shared typed Custom Field system. Historically used custom fields/options are retired rather than physically deleted.

The Workforce module must not create customer-specific columns or database tables for ordinary configurable attributes.

## Configuration hierarchy

Workforce uses the common effective-configuration hierarchy:

```text
Platform Default
→ Company
→ Project Template
→ Project
→ User Preference
```

Current registered rules include:

- standard Worker field presentation/requirements;
- timecard week-start day;
- cost-code requirement;
- overtime availability;
- double-time availability;
- maximum daily hours;
- whether approval is required;
- shared Workflow definition and transition keys;
- personal timecard list columns.

A submitted timecard stores only the small configuration context needed to preserve historical meaning. Future changes to company/project rules do not reinterpret an already submitted or approved timecard.

## Worker and crew lifecycle

Workers use active, inactive and terminated lifecycle states. Ordinary application behavior does not hard-delete historical Worker identity that is referenced by timecards or staffing records.

Crew membership is effective-dated and versioned. Ending membership updates the end date with optimistic revision protection; it does not delete the historical fact that the Worker belonged to the crew.

Crews can be deactivated without deleting their historical membership or project assignment references.

## Project assignment

A Worker must be explicitly assigned to a Project before a project timecard can be created.

The database enforces tenant-safe Project, Worker and Project Worker Assignment relationships. A Worker assigned only to Project A cannot receive a Project B timecard through a forgotten API/service check.

Project assignment supports trade, project role, default cost code, crew, start/end dates and active/suspended/ended status. These fields are business context and can later integrate with Scheduling, Daily Reports, Job Cost and payroll export packages.

## Timecard lifecycle

Timecard business state is revision protected. Draft/rejected timecards can be edited; submitted review behavior is controlled by effective configuration.

For a simple company with approval disabled:

```text
Draft → Submit → Approved
```

For an enterprise with approval enabled:

```text
Draft → Submit → In Review
                     ↓
              shared Workflow
                ↙       ↘
            Reject     Approve
              ↓           ↓
           Rework      Approved
```

Approval is not a separate Workforce approval engine. Workforce starts and transitions the shared Workflow/Approval engine configured for the project.

Timecard history is append-oriented and records business lifecycle events separately from the global Audit log.

## Time entries

Time values use fixed precision Decimal database columns. Floating-point hours are not used.

A time entry belongs to exactly one tenant-owned timecard and records:

- work date;
- regular hours;
- overtime hours;
- double-time hours;
- cost code;
- location;
- work description;
- source type/reference.

The effective project configuration controls whether cost code, overtime and double time are allowed and the maximum daily hours. Entries must fall inside the selected timecard week.

The physical table is `workforce_time_entries`; the legacy unsafe scaffold table `time_entries` is intentionally not recreated.

## Authorization

Atomic capabilities are:

- `workforce.worker.view`
- `workforce.worker.manage`
- `workforce.crew.view`
- `workforce.crew.manage`
- `workforce.assignment.view`
- `workforce.assignment.manage`
- `workforce.timecard.view`
- `workforce.timecard.create`
- `workforce.timecard.update`
- `workforce.timecard.submit`
- `workforce.timecard.approve`
- `workforce.timecard.manage`

Worker/Crew directory actions are company scoped. Project assignment/timecard permissions are evaluated against the exact project. UI hiding is never treated as authorization.

## Shared platform integrations

Workforce reuses, rather than reimplements:

- Authorization and project scope;
- Company/App Configuration;
- typed Custom Fields/Metadata;
- Workflow/Approval;
- Audit;
- Realtime events;
- Search projections;
- Background Jobs when future imports/exports require them;
- Reporting datasets/views when exposed;
- Offline mutation/idempotency contracts for future field UI;
- retention/governance rules;
- integration gateway/mapping for payroll/accounting exports.

## Search

The shared Search registry contains approved projections for Worker and Timecard entities. Timecard results are project scoped and require `workforce.timecard.view`; Worker results require `workforce.worker.view`.

Search is derived data and never grants access to the underlying entity.

## Deployment / installer behavior

`workforce` is a normal business runtime module with `projects` as its only hard dependency. Field Operations is an optional integration, not a required dependency.

Therefore an existing Construction OS installation can add Workforce later through `setup.ps1` without automatically activating Field Operations or a heavyweight worker profile. The common Alembic migration chain already contains the Workforce schema; runtime activation controls route/search/UI availability.

## Payroll and accounting boundary

Approved timecards are authoritative labor-time input. Country-specific payroll calculations, statutory taxes, benefits, wage rules and accounting posting belong to later payroll/accounting/integration packages.

This separation lets Construction OS support multiple countries and external payroll systems without changing historical time capture.

## Release 1 remaining work

The current work establishes the backend/domain foundation. Release 1 still requires, as applicable:

- responsive Worker/Crew/Project staffing UI;
- configuration-driven Worker forms and custom-field rendering;
- fast field time-entry experience;
- offline timecard draft queue/sync/conflict handling;
- shared Workflow task/reviewer UX;
- notifications for assigned/reviewed timecards;
- import/export and payroll/accounting mapping packages;
- Workforce reporting datasets and production dashboards;
- attachment/comment surfaces where required by final workflows;
- configuration health rules for incompatible time policies;
- cross-tenant/project end-to-end authorization tests;
- accessibility, performance and field usability acceptance.

The Feature Registry remains `PLANNED` until those customer-facing Release 1 requirements are complete.
