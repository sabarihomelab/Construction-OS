# RFI Module Contract

## Purpose

The RFI module provides project-scoped, traceable Requests for Information without duplicating controlled drawing, specification, document, workflow, file, notification, or project-access data.

An RFI is a business record with its own lifecycle and append-oriented history. References point to authoritative records owned by other modules.

## Core objects

- `RFI` — current business state, project identity, number, subject, question, due date, priority, ball in court, lifecycle timestamps, optimistic version.
- `RFIResponse` — append-only proposed/official response history. A newer official response supersedes the prior official response; it does not rewrite it.
- `RFIReference` — typed link to an authoritative drawing revision, specification section, document revision, and later schedule activity/change event.
- `RFIHistoryEvent` — business timeline of create/open/update/response/responsibility/close/void actions.
- `RFIProjectCounter` — atomic project numbering state.

Attachments remain managed by File & Media through entity links to `rfi`; file bytes are never stored in RFI tables.

## Tenant and project isolation

Every RFI belongs to one organization and one project.

All API reads and writes derive organization identity from the authenticated Construction OS session. Browser payloads cannot choose the organization.

Project permissions are evaluated for the exact project. A permission granted on Project A does not grant RFI access on Project B.

Ball-in-court responsibility is constrained to a project membership belonging to the same project and organization. Service validation also requires the project membership to be active.

Drawing, specification and controlled-document references must belong to the same project as the RFI.

## Numbering

RFI numbers are allocated per project using an atomic PostgreSQL upsert/returning operation. Concurrent creation must not rely on `MAX(number) + 1`.

The stored number is stable business identity. Future project/company display configuration may add prefixes or formatting without changing historical stored numbers.

## Lifecycle

Initial lifecycle:

`DRAFT -> OPEN -> ANSWERED -> CLOSED`

A controlled `VOID` state is also available with a required reason.

Rules:

- Only a draft can be opened.
- Responses are accepted only while the RFI is open or answered.
- An official response moves an open RFI to answered and clears ball in court.
- A later official response may supersede an earlier official response before close; prior response history is retained.
- Only an answered RFI can be closed.
- Void is a controlled terminal outcome and is audited.
- Closed/void records are never physically deleted as a normal workflow action.
- Optimistic `version` checks protect state-changing operations from stale browser/offline updates.

## Ball in court

Ball in court identifies the organization membership currently responsible for the RFI, but database constraints ensure that membership is also assigned to the same project.

When an open RFI is assigned or opened with a responsible member, a recipient-specific `ACTION_REQUIRED` notification is created. Notification delivery follows the shared notification engine, including permission scope, quiet hours and delivery preferences.

## Responses

Responses are separate records rather than one mutable answer column.

Statuses:

- `PROPOSED`
- `OFFICIAL`
- `SUPERSEDED`
- `WITHDRAWN` (reserved for controlled withdrawal behavior)

The official response is part of the historical record and is indexed for permitted project search.

## References

Supported reference types:

- Drawing revision
- Specification section
- Controlled document revision
- Schedule activity (activated when Scheduling is installed)
- Change event (activated when Change Management is installed)
- Custom reference

Cross-module references preserve stable IDs. RFI does not copy titles, drawing geometry, specification text, schedule dates or change values as authoritative data.

## Permissions

- `rfis.rfi.view`
- `rfis.rfi.create`
- `rfis.rfi.update`
- `rfis.rfi.respond`
- `rfis.rfi.close`
- `rfis.rfi.manage`

Permissions can come from organization roles or project-specific roles, but project-role permissions apply only to that project.

## API

The first project-scoped API is rooted at:

`/api/v1/projects/{project_id}/rfis`

It includes list/create/get/update/open, ball-in-court assignment, responses, references, history, close and void operations.

The API never accepts `organization_id` as tenant authority.

## Realtime and search

RFI business changes emit project-scoped realtime events requiring `rfis.rfi.view`.

Search projections contain approved searchable RFI content only and carry:

- organization ownership
- exact project scope
- `rfis.rfi.view` requirement
- entity version
- route hint

Search results never replace the authorized RFI API as the source of truth.

## Workflow integration

The shared Workflow/Approval engine can attach a workflow instance to the RFI by entity type/id. The RFI table does not duplicate workflow state-machine definitions.

Future tenant configuration may define review/official-response routing, escalation and approval behavior. A running workflow remains tied to its historical workflow version if admins later change the configuration.

## Due dates and escalation

`due_date` is a date-only business value and is not converted through UTC.

Future reminder/escalation policies must use the project timezone and versioned configuration where historical interpretation matters. Overdue state should normally be derived from due date/current project-local date rather than silently rewriting RFI history.

## Files

Attachments use File & Media. Download remains session + tenant + project + permission authorized. Permanent public file URLs are not permitted.

## Offline/mobile

The feature is marked offline-capable because field users must be able to draft questions, capture text/reference intent and continue work with intermittent connectivity.

Before Release 1 UI activation, offline mutation contracts must define temporary client IDs, retry/idempotency behavior, stale-version conflict handling and attachment synchronization.

## Audit/history

Business history records user-visible RFI lifecycle events. Security/audit events remain in the shared Audit service where appropriate, including create and controlled void actions.

History is append-oriented and must not be reconstructed only from the latest RFI row.

## Historical configuration safety

Changes to numbering display, terminology, due-date policy, workflow, notification policy or custom fields apply according to their version/effective date. They must not silently reinterpret issued/closed historical RFIs.

Deactivating related configuration must not destroy existing RFI references or response history.

## Release 1 remaining work

The backend/domain foundation is not the complete Release 1 user experience. Before the feature becomes `AVAILABLE`, Release 1 still requires:

- responsive RFI list/detail/create experience
- field/mobile usability and offline sync behavior
- managed attachment UI
- drawing/specification reference picker and drawing pin workflow
- permission-driven controls and empty/loading/error/conflict states
- configurable workflow/review templates
- notification/reminder/escalation policies
- exports/reports and printable RFI format
- integration with Scheduling and Change Management when those modules are implemented
- full database integration tests and cross-tenant/project authorization tests
- accessibility/help content

Until those are complete, the Feature Registry keeps RFIs in `PLANNED` state so unfinished UI is not exposed as released functionality.
