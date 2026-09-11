# Workforce / Contract Labour / Attendance

## Purpose

Workforce is the India-first labour foundation for Worker identity, crews, project staffing, daily site attendance and governed project time.

It supports direct labour, contract labour, subcontractor labour, vendor crews and staff without turning every Worker into an application User.

The core Release 1 flow is:

```text
Company Worker
→ Project Worker Assignment
→ Crew / employer Party / engagement / trade
→ Daily Attendance Register
→ Approved Attendance
→ DPR crew summary / downstream labour-cost input
```

Weekly Timecards remain available for detailed commercial time capture. They do not replace the faster daily site muster workflow.

## Worker is not User

A `Worker` is a company workforce identity. An `OrganizationMembership` is an application login/access identity.

A Worker may exist with no login at all. This is normal for site labour, contract labour, subcontractor labour, vendor crews, imported worker masters and payroll integrations.

A Worker may optionally link to an Organization Membership, but the link does not grant project access. Project application access remains controlled by Project Membership, Role Assignment and Authorization.

## Object model

```text
Company
├── Worker
│   └── optional Organization Membership / login
├── Crew
│   └── effective-dated Crew Membership
└── Project
    └── Project Worker Assignment
        ├── crew
        ├── employer Party
        ├── engagement type
        ├── project role / trade
        ├── effective-dated commercial rates
        ├── Daily Attendance Entry
        └── Weekly Timecard
```

A Worker belongs to the company and may be assigned to multiple projects without duplicating identity.

## Project assignment

A Worker must be assigned to a Project before attendance or project time can be recorded.

Project Worker Assignment carries project-specific context:

- crew;
- employer Party;
- engagement type (`staff`, `direct_labour`, `contract_labour`, `subcontractor_labour`, `vendor_crew`, `other`);
- project role;
- trade;
- assignment dates;
- active/suspended/ended state;
- legacy default cost-code text where still present.

Attendance itself can use the authoritative project WBS / Cost Code foreign key. The attendance service does not rely on free-text cost code when WBS allocation is required.

## Daily attendance / muster

Daily attendance is the field-first source of truth for who worked on site.

One `AttendanceRegister` exists per:

```text
Project + Attendance Date + Shift
```

Creating a register can automatically populate all active Project Worker Assignments valid on that date. This avoids supervisors typing the same Worker list every day.

Each attendance entry records:

- exact Project Worker Assignment;
- Worker;
- crew;
- employer Party;
- engagement type;
- trade;
- attendance mark;
- regular hours;
- overtime hours;
- optional authoritative WBS / Cost Code;
- location;
- notes;
- source type/reference;
- immutable context snapshot.

Supported marks are:

- `not_marked`;
- `present`;
- `absent`;
- `half_day`;
- `leave`;
- `weekly_off`.

Non-working marks cannot carry work hours. Daily hours are constrained by the effective Workforce configuration.

## Why attendance snapshots context

Crew, trade, employer and engagement can change later on the Project Worker Assignment.

An approved attendance record must still mean what it meant on the attendance date. Therefore each attendance entry snapshots the assignment/Worker context used when the register was edited.

Historical attendance is not reinterpreted when the Worker changes crew, employer or trade later.

## Attendance lifecycle

Attendance is revision protected.

With approval disabled:

```text
Draft → Submit → Approved
```

With approval enabled:

```text
Draft → Submit → In Review
                     ↓
              shared Workflow
                ↙       ↘
            Reject     Approve
              ↓           ↓
           Rework      Approved
```

Attendance does not create a private approval engine. It uses the shared Workflow engine configured for the project.

Draft/rejected registers can be edited. Approved registers cannot be silently rewritten through the normal edit API.

Attendance business lifecycle events are append-oriented in `workforce_attendance_history_events` in addition to the global Audit log.

## Configurable rules

Attendance uses the common configuration hierarchy:

```text
Platform Default
→ Company
→ Project Template
→ Project
→ User Preference
```

Registered attendance rules include:

- whether WBS / Cost Code is required for working marks;
- whether attendance approval is required;
- shared Workflow definition key;
- approve transition key;
- reject transition key;
- resubmit transition key.

The register snapshots the relevant effective configuration context when submitted so future rule changes do not rewrite historical meaning.

Existing Timecard configuration remains independent and continues to control week start, overtime, double time, maximum hours, approval and timecard workflow transitions.

## DPR integration

Approved attendance exposes a DPR-ready crew summary grouped by:

- employer Party;
- crew;
- trade.

The summary contains Worker count, present count, absent count, regular hours and overtime hours.

This is intentionally a derived contract. Workforce does not create duplicate DPR crew rows by itself. The Field/DPR workflow can consume the approved attendance summary when the DPR module is completed/refit.

No DPR summary is exposed from draft/rejected/in-review attendance.

## Project Worker commercial rates

Commercial worker rates remain effective-dated on the exact Project Worker Assignment.

Supported wage bases include hourly, daily, weekly, monthly, piece-rate and contract.

Rates are sensitive. Daily attendance responses do **not** expose:

- regular cost rate;
- overtime rate;
- double-time rate;
- billing rate;
- wage basis.

A supervisor can therefore mark attendance without being allowed to view Worker commercial rates.

Downstream Job Cost may combine approved attendance/time with an applicable governed rate when the wage basis can be calculated safely. Workforce does not invent conversions for monthly/weekly/contract wages and does not post accounting entries itself.

## Weekly Timecards

Weekly Timecards remain the detailed time-entry workflow for companies that need them.

They support:

- project/Worker/week uniqueness;
- regular/overtime/double-time hours;
- cost-code/location/work description;
- configuration-driven validation;
- shared Workflow approval;
- append-oriented history;
- search projection.

Daily Attendance and Weekly Timecards have different field UX purposes. They must not become two independent sources of truth for the same downstream cost without an explicit integration rule.

## Authorization

Existing Workforce permissions continue for Worker, Crew, Assignment, Rate and Timecard actions.

Daily Attendance adds project-scoped capabilities:

- `workforce.attendance.view`
- `workforce.attendance.create`
- `workforce.attendance.update`
- `workforce.attendance.submit`
- `workforce.attendance.approve`

UI visibility never replaces server-side authorization.

## Platform integrations

Workforce reuses:

- tenant/project isolation;
- Authorization;
- Configuration;
- shared Workflow/Approval;
- Audit;
- realtime Events;
- Search for existing Worker/Timecard projections;
- Party directory for labour employer context;
- WBS / Cost Codes for authoritative cost allocation;
- offline infrastructure for future field sync hardening.

`workforce` remains a normal runtime module with `projects` as its only hard dependency. Commercial and Field are optional integrations.

## Payroll / statutory boundary

Construction OS Release 1 does not become a payroll engine here.

Workforce does not calculate country-specific payroll taxes, PF/ESI, labour-law statutory deductions, benefits, payslips or GL entries.

Its responsibility is authoritative labour identity, project assignment, attendance/time evidence and governed commercial context for downstream project controls and integrations.

## Release 1 Module 5 completion

Module 5 now provides:

- Worker master independent of application User;
- Crew lifecycle and effective membership;
- multi-project Worker assignment;
- employer Party and engagement context;
- effective-dated sensitive Worker rates;
- weekly governed Timecards;
- daily India-first attendance/muster registers;
- bulk active-worker population;
- fast field marking and hours;
- WBS-aware allocation;
- configurable shared Workflow approval;
- append-oriented attendance history;
- immutable assignment context snapshots;
- approved DPR summary contract;
- responsive Worker / Staffing / Attendance workspace;
- project and attendance deep-link routes.

Further cross-module work belongs to later modules: DPR consumption of the approved summary, governed labour-cost posting, reporting dashboards, import/export/payroll adapters and offline hardening.
