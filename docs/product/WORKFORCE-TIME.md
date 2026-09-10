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
        ├── project role / trade / crew
        ├── optional employer Party and engagement type
        ├── effective-dated Project Worker Rates
        └── Weekly Timecard
            ├── Time Entries
            ├── shared Workflow instance when approval is enabled
            └── append-oriented history
```

A Worker can exist without a Construction OS login. This is required for subcontract labor, field workers who do not use the application directly, imported workforce records and future payroll/integration scenarios.

A Worker belongs to the company, not to one project. The same Worker can be assigned to multiple Projects without duplicating worker identity. Each Project Worker Assignment carries that project's role, trade, crew, engagement/employer context, dates and status.

Worker assignment and application visibility are separate concepts. Assigning a Worker to Project A does not create a login or grant access to Project A. Application users receive project visibility only through Project Membership, Role Assignment and Authorization. Likewise, a Worker assigned to Projects A and B can have an application user that is allowed to see only Project A.

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

## Multi-project worker assignment

A Worker must be explicitly assigned to a Project before a project timecard can be created.

The database enforces tenant-safe Project, Worker and Project Worker Assignment relationships. A Worker assigned only to Project A cannot receive a Project B timecard through a forgotten API/service check.

Project assignment supports trade, project role, default cost code, crew, start/end dates and active/suspended/ended status. It can also identify the project-specific engagement type such as staff, direct labour, contract labour, subcontractor labour or vendor crew.

Where labour is supplied by another business, `employer_party_id` can point to the company-level Party directory. The relationship is optional so the Workforce module remains usable for direct employees even when Commercial workflows are not active.

The same Worker may have different project context. For example, one Worker may be a carpenter in Project A and a crew supervisor in Project B, with different crews and commercial rates. These are assignment facts and do not duplicate the Worker master.

## Project worker commercial rates

Commercial rate information is effective-dated and belongs to the exact Project Worker Assignment. It is not stored on the company Worker master because the same Worker may have different rates in different projects or periods.

Supported wage bases are hourly, daily, weekly, monthly, piece-rate and contract. A rate record can hold regular cost rate plus optional overtime, double-time and billing rates. Monetary values use Decimal database columns.

Rate periods must not overlap for the same Project Worker Assignment. Historical rates are ended with an effective date and retained rather than overwritten. Downstream Job Cost should resolve the rate applicable to the work date and persist the resulting cost/rule context so a later rate change does not rewrite historical cost.

Worker rates are sensitive commercial information. They are not included in ordinary Worker or assignment responses and require separate project-scoped permissions:

- `workforce.rate.view`
- `workforce.rate.manage`

A supervisor can therefore be permitted to assign workers and approve attendance without being allowed to see wage or billing rates.

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
- `workforce.rate.view`
- `workforce.rate.manage`
- `workforce.timecard.view`
- `workforce.timecard.create`
- `workforce.timecard.update`
- `workforce.timecard.submit`
- `workforce.timecard.approve`
- `workforce.timecard.manage`

Worker/Crew directory actions are company scoped. Project assignment, project worker rate and timecard permissions are evaluated against the exact project. UI hiding is never treated as authorization.

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
- integration gateway/mapping for payroll/accounting exports;
- the shared Party directory when an external labour employer needs to be identified.

## Search

The shared Search registry contains approved projections for Worker and Timecard entities. Timecard results are project scoped and require `workforce.timecard.view`; Worker results require `workforce.worker.view`.

Sensitive Project Worker Rates are intentionally not exposed through the ordinary Worker search projection.

Search is derived data and never grants access to the underlying entity.

## Deployment / installer behavior

`workforce` is a normal business runtime module with `projects` as its only hard dependency. Field Operations, Equipment, Safety and the Commercial Party directory are optional integrations, not required dependencies.

Therefore an existing Construction OS installation can add Workforce later through `setup.ps1` without automatically activating those optional modules or a heavyweight worker profile. The common Alembic migration chain already contains the Workforce schema; runtime activation controls route/search/UI availability.

## Payroll, Job Cost and accounting boundary

Approved timecards are authoritative labor-time input. Project Worker Rates provide governed commercial context for Job Cost, but Workforce does not post accounting entries itself.

Job Cost can combine approved time with the effective project rate and retain a source reference back to the Worker assignment/time entry. Country-specific payroll calculations, statutory taxes, benefits, wage rules and general-ledger posting belong to later payroll/accounting/integration packages.

This separation lets Construction OS support multiple projects, labour suppliers and external payroll/accounting systems without changing historical time capture.

## Release 1 remaining work

The current work establishes the backend/domain foundation. Release 1 still requires, as applicable:

- responsive Worker/Crew/Project staffing UI;
- configuration-driven Worker forms and custom-field rendering;
- fast field time-entry experience;
- offline timecard draft queue/sync/conflict handling;
- shared Workflow task/reviewer UX;
- notifications for assigned/reviewed timecards;
- import/export and payroll/accounting mapping packages;
- Workforce and labour-cost reporting datasets and production dashboards;
- attachment/comment surfaces where required by final workflows;
- configuration health rules for incompatible time policies;
- cross-tenant/project end-to-end authorization tests;
- accessibility, performance and field usability acceptance.

The Feature Registry remains `PLANNED` until those customer-facing Release 1 requirements are complete.
