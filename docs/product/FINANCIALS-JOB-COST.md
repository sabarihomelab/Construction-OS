# Financials / Job Cost

## Purpose

Financials / Job Cost is the governed financial-control layer between Construction OS operational records and an external accounting book such as TallyPrime.

Release 1 does not attempt to replace statutory accounting. Construction OS owns construction-commercial truth: commitments, site expenses, actual project cost, client billing/receipts, traceability and accounting-ready mappings. Statutory books, returns and organization-specific accounting policy remain in the accounting system and with the contractor's finance/CA process.

## Core separation

The product deliberately keeps three concepts separate:

```text
Construction Cost Head = what the project spent money on
WBS / BOQ             = where / against what work the cost belongs
Ledger Account        = how finance/accounting classifies the posting
```

For example, `Equipment > Fuel / Diesel` can be a company-defined Cost Head. The same Cost Head can be allocated to different projects, WBS packages or equipment records. It can then be mapped, with effective dates, to the company's chosen accounting ledger.

This avoids hardcoding one contractor's expense names into the product while preserving consistent reporting categories and accounting integrity.

## Company-defined cost heads

Cost Heads are organization-owned hierarchical masters. A company may create names and subheads that fit its operating model, for example:

```text
Material
Labour
Equipment
  Fuel / Diesel
  Hire Charges
Subcontract
Site Expense
  Local Transport
  Loading / Unloading
  Small Tools
Indirect
Other
```

The category enum is controlled by the platform; the company's codes, names and hierarchy are configurable. Historically referenced Cost Heads are deactivated rather than deleted from financial history.

Ordinary site users select configured Cost Heads. Creating and restructuring Cost Heads is a high-risk company administration capability.

## Ledger accounts and mapping

Ledger Accounts provide a controlled accounting classification using the stable accounting types Asset, Liability, Equity, Income and Expense.

Cost Head to Ledger mapping is a separate effective-dated relationship. Changing a future mapping does not rewrite the meaning of historical project-cost entries. This also allows accounting adapters to translate Construction OS records to TallyPrime, CSV or another accounting system without embedding Tally-specific behavior in construction modules.

No GST, withholding/TDS, e-invoice threshold or statutory percentage is hardcoded in this foundation. Those rules must be versioned/effective-dated and verified against the applicable period before they become authoritative calculations.

## Project cost ledger

`ProjectCostEntry` is the common project actual-cost envelope. It identifies the authoritative source and carries one or more `ProjectCostAllocation` lines.

Supported source categories include workforce time, material consumption, equipment usage, subcontract claims, goods receipts/vendor bills where commercial policy says they become cost, site expenses and controlled adjustments.

Operational modules remain authoritative for their source facts. Job Cost references those facts; it must not ask users to re-enter the same attendance, material, equipment or subcontract information.

A project-cost allocation can reference:

- company Cost Head;
- project WBS;
- project BOQ item;
- Party;
- the exact Project Worker Assignment;
- equipment asset;
- material;
- quantity/unit and money amount.

The Project Worker Assignment relationship is important for multi-project companies: one company Worker can work on several projects, but a labour-cost allocation can reference only the assignment for the project being costed.

## Multi-project and access model

Company identity and project participation are separate:

```text
Organization
├── Project A
├── Project B
└── Project C

Worker Ravi
├── Assignment: Project A
└── Assignment: Project B

User Ravi (optional login)
├── Project Membership: Project A
└── no Project B application access unless separately granted
```

Being a Worker or being assigned to a project never grants application visibility. API access continues to use Organization Membership, Project Membership, Project Role and atomic permissions.

Financial permissions are intentionally more restrictive than normal workforce/project visibility. A supervisor can be allowed to create a site expense without receiving ledger-management, worker-rate or financial-posting authority.

## Site cash

Site cash is modeled as a project account with append-oriented transactions. The balance is derived from transaction history rather than stored as an editable balance.

```text
Advance / top-up       → inflow
Approved cash expense  → outflow
Return to company      → outflow
Refund                 → inflow
Controlled adjustment  → explicit transaction
```

A cash advance is not an expense. It becomes project cost only when an approved expense is posted against a Cost Head/WBS allocation.

A Worker selected as the site-cash custodian must be actively assigned to the project. An application membership selected as custodian must be an active member of that project.

The initial posting service prevents a site-cash expense from taking the derived account balance below zero. If the product later supports a contractor policy that allows reimbursement-before-funding, that behavior must be an explicit versioned company/project rule rather than a silent fallback.

## Site expense lifecycle

The initial lifecycle is:

```text
Draft → Submitted → Approved → Posted
              ↘ Rejected → rework / resubmit
```

A draft contains the user-facing facts: date, amount, payee when known, payment method/reference, optional site-cash account and explicit Cost Head/WBS/BOQ allocations.

Submission revalidates that allocations still total the header amount and that referenced Cost Heads/WBS/BOQ items are valid. Approval is a separate permission. Posting is a critical permission.

Posting an approved cash expense is transactional. In the same database transaction the service:

1. creates the posted `ProjectCostEntry`;
2. copies the approved allocation basis to `ProjectCostAllocation`;
3. creates the site-cash outflow when a site-cash account was used;
4. marks the expense Posted;
5. records a critical audit event and project-scoped event.

If any part fails, the caller rolls back the entire operation rather than leaving cash and job cost inconsistent.

The shared configurable Workflow engine can later replace the simple one-step approval transition for contractors that need multi-level approval. The stored business objects and permission boundaries do not depend on a fixed approval chain.

## Visibility examples

A practical default role design can be configured as:

```text
Site Supervisor
- create/view permitted site expenses
- view assigned site cash if required
- no ledger setup
- no worker commercial-rate access
- no final financial posting

Project Manager / QS
- project job-cost visibility as granted
- site-expense approval as granted
- no company ledger administration unless explicitly assigned

Finance / Company Admin
- cost-head and ledger setup
- accounting mappings
- critical posting/reversal permissions
- cross-project reporting only where organization role permits
```

These are starter role patterns, not hardcoded job titles.

## Current backend foundation

The current foundation includes:

- governed Ledger Accounts and balanced journal persistence;
- project commitments from issued purchase orders and work orders;
- client invoice/receipt persistence with certified-RA lineage and allocation controls;
- company Cost Heads;
- effective-dated Cost Head to Ledger mappings;
- project-cost entries and allocations;
- certified subcontract claim cost feeds plus a non-duplicating payable projection;
- project site-cash accounts and transaction ledger;
- site expenses and allocations;
- shared Workflow approval for site expenses and vendor bills while preserving domain validation/posting rules;
- controlled accounting export preview with an Excel-compatible cost-register CSV;
- a TallyPrime adapter contract based only on posted balanced journal entries;
- project commercial control across Budget, Commitment, Actual Cost, Certified/Billed, Issued Receivable, Received and Outstanding Receivable;
- versioned India tax/withholding rule snapshots on governed client invoicing;
- permission-scoped APIs for Cost Heads, ledgers, site cash, site expenses, payables, receivables, accounting export and job-cost reporting;
- audit/events for implemented write flows;
- permission-scoped search projections;
- Alembic migration and structural tests.

## Remaining Release 1 work

This foundation is not the end of Financials. Follow-on work must connect approved operational events without duplicating data, including:

- approved workforce time → labour cost using the effective Project Worker Rate;
- material consumption/store ledger → material actual cost;
- equipment usage/hire/fuel → equipment actual cost;
- generated Excel workbook packages in addition to the current Excel-compatible CSV surface;
- concrete TallyPrime transport/import packaging on top of the governed adapter contract;
- receipt/file attachment UX using the shared Files module;
- mobile/offline site-expense capture;
- reversal/correction workflows that preserve the original history;
- deeper authorization, migration, concurrency and transaction tests.

No customer-facing Financials feature should be marked Available merely because these backend tables and routes exist. It remains PLANNED until the integrated India project journey and release Definition of Done are satisfied.
