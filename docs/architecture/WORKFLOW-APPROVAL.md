# Workflow and Approval Engine

## Purpose

Construction OS uses one shared versioned workflow engine for business processes such as RFIs, Submittals, Change Management, Invoices, Time approvals, Safety actions, Closeout and other approval/state-driven modules.

Business modules add their own domain validation, but they must not independently invent state history, approval sequencing, stale-write handling, permission checks or workflow versioning.

## Core structure

```text
WorkflowDefinition
      ↓
WorkflowVersion
      ├── States
      └── Transitions

Business record
      ↓
WorkflowInstance (pinned to one WorkflowVersion)
      ↓
Transition / Approval Request
      ↓
History + Audit + Realtime event
```

## Historical behavior

Published workflow versions are immutable business context for existing instances.

If an administrator publishes Workflow v4:

- new eligible records start on v4;
- records already started on v3 remain on v3;
- v3 is retired for new starts but retained for historical/running records;
- old history is never rewritten to match v4.

This prevents configuration changes from silently changing historical or in-flight business meaning.

## Definitions and versions

A definition has a stable tenant-scoped key and target entity type, for example:

```text
rfi.standard
submittal.standard
invoice.approval
change.owner_approval
```

A version contains the configuration used for one published workflow generation.

Only draft versions are editable. Publishing validates the graph, retires the previous active version for new starts and records audit/realtime events.

## States

State kinds are:

- `initial`
- `active`
- `completed`
- `cancelled`

A published workflow has exactly one initial state.

Completed/cancelled terminal states cannot define outgoing transitions.

State keys are stable machine identifiers. Labels may be localized/configured without changing historical keys.

## Transitions

A transition identifies:

- from state;
- to state;
- required domain permission if any;
- whether a reason is mandatory;
- whether step-up MFA is mandatory;
- optional domain conditions;
- optional approval policy;
- assignment rule;
- due/escalation rule.

Backend authorization is authoritative. Hiding a button in the UI never grants or removes the right to execute a transition.

## Domain conditions

The generic workflow engine does not interpret arbitrary construction/accounting rules itself.

Example:

```text
Transition: approve_change
Workflow checks:
- current state
- permission
- reason
- MFA
- approval completion

Change Management domain checks:
- required quote exists
- cost impact balanced
- owner amount within authorized rules
- required attachments present
```

If a transition contains domain conditions, the trusted business-module service must explicitly confirm those conditions before the engine executes it. Missing confirmation fails closed.

## Optimistic concurrency

Every workflow instance has a monotonically increasing version.

Clients and offline mutations submit the version they acted on. If the server has advanced, the transition fails with a conflict rather than silently overwriting the newer state.

Example:

```text
User A sees instance version 7
User B transitions → version 8
User A submits action against version 7
→ conflict
→ refresh/review required
```

This is required for realtime multi-user editing and offline synchronization.

## Approval requests

Approval-required transitions create a durable `WorkflowTransitionRequest` pinned to:

- workflow instance;
- transition;
- source state;
- target state;
- expected instance version;
- requester;
- reason/context.

Approvals are not represented merely as comments or boolean fields.

## Approval tasks

Approval tasks support assignee types:

- user;
- role;
- project role;
- external scoped approver.

Tasks may have ordered sequence numbers and due dates.

Release 1 supports sequential approval semantics. Earlier sequences must be approved before later sequences can act.

A rejection resolves the request as rejected and cancels remaining pending tasks. A requester may cancel a still-pending request where domain policy permits.

## Stale approval protection

Approval and execution are intentionally separate.

After all approvals are received, the final execution step rechecks:

- workflow instance still exists/active;
- current state is unchanged;
- instance version matches the version approval was requested against;
- required permission is currently valid;
- step-up authentication if required;
- domain conditions against current business data.

If the record changed during the approval period, the previously approved request does not blindly execute.

## Audit and history

`workflow_history_events` is append-oriented and records each executed transition with:

- instance version;
- transition key;
- from/to state;
- actor;
- reason;
- timestamp;
- correlation ID;
- bounded event context.

Security/business audit records are emitted separately through the shared Audit service.

History records are not rewritten because labels/configuration change later.

## Realtime behavior

Successful workflow actions emit small committed events such as:

```text
workflow.instance.changed
workflow.approval.changed
workflow.definition.changed
```

Connected clients invalidate/refetch the affected authorized record instead of receiving sensitive full business objects through the realtime channel.

## Offline behavior

Business modules may permit selected workflow actions offline only when their module contract says the action is safe offline.

Offline submissions carry:

- client mutation ID;
- expected entity/workflow version;
- actor/device context;
- transition key;
- required domain input.

The server revalidates permission, workflow state, approval requirements and domain rules on sync. It never assumes an offline button press is authoritative.

High-risk actions such as financial posting, critical approvals or step-up-MFA transitions may be online-only even when the surrounding record supports offline editing.

## Notifications and escalation

Workflow due/escalation rules feed the shared Notification and Background Jobs services.

Examples:

- RFI answer overdue;
- submittal review due tomorrow;
- invoice approval pending;
- change quote awaiting response.

Notification content and recipients remain permission-scoped.

## Admin configuration

Capabilities:

- `admin.workflow.view`
- `admin.workflow.manage`

Admin tooling will eventually provide:

- workflow templates;
- visual/list state and transition editing;
- permission/condition configuration;
- approval routing;
- due/escalation rules;
- validation before publish;
- version comparison;
- impact explanation;
- preview/test of future workflows.

Admins do not directly mutate a published historical version. They create the next draft and publish it when ready.

## Release 1 consumers

The engine is intended to support at minimum:

- RFIs;
- Submittals;
- Daily Report submission/approval where configured;
- Time and workforce approvals;
- Safety/inspection corrective actions;
- Bid/estimate approvals where configured;
- Change Management;
- Purchase orders/commitments;
- invoices and financial approvals;
- Closeout acceptance.

Each consuming module defines its domain-specific transitions, conditions, permissions, notification rules and offline restrictions in its own module contract.
