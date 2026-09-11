# Estimate / Rate Analysis / Budget

## Purpose

Module 4 turns approved contractual scope into the contractor's governed internal cost and budget baseline.

It preserves three separate meanings:

- **BOQ** — contractual scope, quantity and contract rate.
- **Estimate / Rate Analysis** — contractor's internal build-up of cost and selling rate.
- **Budget** — approved project cost baseline used for cost control.

A BOQ rate is never silently copied as internal cost.

## India Release workflow

```text
Approved BOQ
    ↓
Estimate draft
    ↓
BOQ scope copied (optional)
    ↓
Rate analysis per estimate item
    ├─ Material
    ├─ Labour
    ├─ Equipment
    ├─ Subcontract
    ├─ Overhead component
    └─ Other
    ↓
Wastage + overhead + profit calculation
    ↓
Estimate submit
    ↓
Estimate approval snapshot
    ↓
Cost budget generation
    ↓
Budget approval snapshot
    ↓
Current approved project budget baseline
```

Manual estimates are also supported where a project scope is not sourced from a BOQ.

## Rate analysis meaning

For a rate analysis:

1. component amounts produce the base rate;
2. wastage is added to base cost;
3. overhead percentage is applied after wastage;
4. profit is applied after cost and overhead;
5. selling rate includes profit.

The approved project **cost budget excludes profit**.

Example:

```text
Base rate              150.00
Wastage 10%             15.00
Cost after wastage     165.00
Overhead 20%            33.00
Cost rate              198.00
Profit 10%              19.80
Selling rate           217.80
```

The budget consumes 198.00 per unit, not 217.80.

## Configurable defaults

Company/project configuration may propose defaults for:

- wastage percentage;
- overhead percentage;
- profit percentage.

Those defaults do not rewrite historical records. Each approved estimate snapshot stores the actual percentages and component values used.

## BOQ relationship

An estimate may reference an approved BOQ.

When BOQ items are copied:

- quantity, unit, item identity, WBS and BOQ lineage are retained;
- the internal estimate rate starts at zero;
- rate analysis is required before estimate approval;
- BOQ contract rate remains contractual information and is not treated as internal cost.

Only an approved BOQ may be used as a source.

## WBS requirement

Every estimate item must have an active WBS code before estimate approval.

This is required because an approved estimate must be capable of producing a complete project cost budget. The budget generator must never silently discard an estimate item because it has no WBS allocation.

## Estimate lifecycle

```text
Draft → Submitted → Approved
```

Approved estimates are not edited in place.

To change an approved estimate, an authorized user creates a revision draft. The revision clones the estimate items and current rate-analysis evidence. The prior approved estimate stays approved until the replacement revision is approved. Approval of the replacement marks the prior estimate as superseded.

## Estimate approval snapshot

Approval creates immutable historical evidence containing:

- estimate identity and revision;
- source BOQ reference;
- WBS references and codes;
- item quantities;
- current rate-analysis version;
- all rate-analysis components;
- wastage, overhead and profit percentages;
- base, cost, profit and selling rates;
- extended cost/profit/selling values;
- WBS/category cost breakdown used to generate the budget.

Later configuration or rate-analysis changes cannot reinterpret the approved snapshot.

## Budget generation

A budget generated from an estimate uses the latest immutable approval snapshot, not mutable draft tables.

Budget lines are grouped by:

```text
WBS × Cost Category
```

Categories are:

- material;
- labour;
- equipment;
- subcontract;
- overhead;
- other.

Wastage is allocated proportionally across the underlying base cost categories. Percentage overhead is recorded in the overhead category. Profit is excluded.

The generated budget total must reconcile exactly to the approved estimate cost total before it can be persisted.

## Budget lifecycle

A draft budget may be reviewed before approval.

Approval:

- requires at least one budget line;
- creates an immutable budget approval snapshot;
- links back to the estimate approval snapshot where applicable;
- marks any previously approved project budget as superseded;
- makes the newly approved budget the current project cost baseline.

Historical approved/superseded budgets remain queryable.

## Permissions

Module 4 reuses the existing atomic permissions:

- `estimating.module.view`
- `estimating.estimate.view`
- `estimating.estimate.manage`
- `estimating.estimate.submit`
- `estimating.estimate.approve`
- `estimating.rate_analysis.manage`
- `estimating.budget.view`
- `estimating.budget.manage`
- `estimating.budget.approve`

The backend remains authoritative for company/project scope.

## Audit, realtime and search

High-risk actions are audited, including estimate approval, revision creation and budget approval.

Estimate and budget changes use the shared outbox/realtime system and approved search projections. Realtime payloads contain identity/revision information only; clients refetch through authorized APIs.

Search routes deep-link to:

- `/projects/{projectId}/estimating/estimates/{estimateId}`
- `/projects/{projectId}/estimating/budgets/{budgetId}`

## Historical safety

The module does not:

- modify an approved BOQ;
- treat BOQ contract rate as internal cost;
- rewrite an approved estimate in place;
- recalculate historical snapshots from current configuration;
- include profit in project cost budget;
- silently omit estimate items without WBS;
- maintain multiple approved project budgets as if all were current.

## Non-goals

Module 4 is not:

- procurement;
- job-cost actual posting;
- general ledger accounting;
- client billing;
- statutory GST/TDS calculation;
- scheduling.

Those modules consume the approved scope/cost baseline where appropriate but retain their own authoritative business events.
