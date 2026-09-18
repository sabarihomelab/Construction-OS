# Agent Execution Policy — Fast Development

This document is the execution policy for coding agents working on Construction OS.

Read this before starting implementation work.

## Goal

Keep development fast without weakening quality.

Do **not** run the complete repository validation cycle after every small change. Validate the smallest affected scope during development, then perform broader validation only at meaningful completion boundaries.

---

## 1. Choose the execution level first

Before changing code, classify the request into one of these levels.

### LEVEL 1 — MICRO

Use for:
- small bug fixes
- UI/text/layout changes
- small validation changes
- one endpoint/service adjustment
- one focused test fix

Execution:
1. Inspect only the impacted files and direct dependencies.
2. Implement the change.
3. Run only directly relevant tests.
4. Run changed-area lint/type checks when applicable.
5. Do not run full repository CI.
6. Do not run a production frontend build unless the change specifically requires it.
7. Do not rebuild Docker images unless Docker/runtime/dependency files changed.

Stop when the focused change and targeted validation pass.

---

### LEVEL 2 — FEATURE

Use for one bounded feature or workflow slice.

Examples:
- Material Master
- Site Store
- Material Issue
- Stock Transfer
- Indent creation
- RFQ comparison

Execution:
1. Inspect the feature area and direct cross-module dependencies.
2. Implement the required model/service/API/UI/migration pieces for that feature only.
3. Run feature/unit tests.
4. Run directly affected integration tests.
5. Run relevant migration checks if schema changed.
6. Do not run unrelated module tests.
7. Do not run full repository CI.
8. Do not run production frontend build unless required for this feature.

Stop when the feature slice is working and its targeted validation passes.

---

### LEVEL 3 — MODULE COMPLETE

Use when finishing a complete module.

Examples:
- Inventory module complete
- Procurement module complete
- Equipment module complete

Execution:
1. Verify all module requirements are implemented.
2. Run the complete module test suite.
3. Run cross-module integration tests affected by the module.
4. Validate migrations for the module.
5. Run backend lint/type checks as applicable.
6. Run frontend production build when the module includes web changes.
7. Verify permissions, audit, validation, workflow/state rules, indexes, documentation, and required UI.
8. Update DEV-WORKS and module documentation.

Only after these checks pass may the agent declare the module complete.

---

### LEVEL 4 — CHECKPOINT / RELEASE

Use for:
- major milestone
- release preparation
- merge-ready checkpoint
- several completed modules
- explicit request for full validation

Execution:
1. Run the full backend test suite.
2. Run full frontend production build.
3. Validate clean-database migrations.
4. Validate upgrade migrations.
5. Run repository-wide integration tests.
6. Run lint/type/static checks.
7. Run CI-equivalent validation.
8. Verify documentation and version/checkpoint state.

This is the appropriate place for the expensive full-repository validation cycle.

---

## 2. Prefer small implementation slices

Do not implement a large module as one huge agent task when it can be safely divided into independent slices.

Example — Inventory:

1. Material Master
2. Material Categories / UOM
3. Site Stores
4. Stock Ledger
5. GRN to Inventory
6. Material Issue
7. Material Consumption
8. Stock Transfer
9. Adjustments
10. Inventory Reporting
11. Module integration validation

Example — Procurement:

1. Indent
2. Approval
3. RFQ
4. Vendor Quote
5. Comparison
6. Purchase Order
7. PO Approval
8. GRN Integration
9. Procurement Reporting
10. End-to-end module validation

Each slice should be implemented and tested independently before moving to the next.

---

## 3. Use incremental validation

During normal development:

- changed service -> service/unit tests
- changed API -> API tests + directly affected integration tests
- changed migration -> migration-specific validation
- changed UI component/page -> targeted frontend checks
- changed shared foundation -> affected module tests

Do not automatically run the entire repository test suite after every edit.

Full validation is required before module completion or release, not after every internal iteration.

---

## 4. Frontend development rule

During normal development use the development server and incremental compilation.

Prefer:

```bash
npm run dev
```

Do not repeatedly run:

```bash
npm run build
```

for every UI change.

Run the production frontend build at MODULE COMPLETE, CHECKPOINT / RELEASE, or when the requested change specifically needs production-build validation.

---

## 5. Backend development rule

Use the existing local development/runtime reload behavior for ordinary Python application changes.

Do not restart/rebuild the complete environment for normal service, API, model, or validation edits unless required.

Run the smallest useful backend test scope first, then expand only when failures or shared dependencies justify it.

---

## 6. Docker rebuild rule

Do not rebuild Docker images for ordinary application-code changes.

A rebuild is normally justified when files such as these change:

- Dockerfile
- dependency manifests / lockfiles
- system/runtime dependencies
- container configuration
- image-level environment configuration

Normal changes to application source files should use the existing development environment whenever possible.

---

## 7. Impact-based expansion

Start narrow and expand validation only when needed.

If a change touches shared code used by multiple modules, identify the direct consumers and test those consumers.

If targeted tests reveal cross-module regressions, widen the test scope.

Do not widen scope merely because a full suite exists.

---

## 8. Agent response before implementation

For non-trivial work, state the selected execution level and intended slice briefly before coding.

Example:

> Execution level: FEATURE. Building Material Issue only. I will inspect inventory/service/API dependencies, implement this slice, run Material Issue and directly affected inventory tests, and avoid full repository CI until module completion.

Do not spend significant time producing a large planning document unless the task requires architecture or impact analysis.

---

## 9. Completion rules

### MICRO complete
- requested change works
- targeted tests pass

### FEATURE complete
- bounded workflow works end-to-end
- targeted unit/integration tests pass
- required migration/UI pieces are included

### MODULE complete
- all module slices are complete
- module and affected integration tests pass
- migration validation passes
- permissions/audit/workflow/index/documentation requirements are satisfied
- relevant production frontend build passes

### RELEASE complete
- repository-wide validation passes
- clean and upgrade migrations pass
- full frontend/backend checks pass
- CI-equivalent checks are green

---

## 10. Default interpretation of the word "build"

When a user says **"build"**, do not automatically interpret it as "run the entire repository build and CI suite."

Interpret it as **implement the requested functionality using the smallest safe execution level**.

Only perform LEVEL 4 full-repository validation when:

- the user explicitly asks for full build/full CI/release validation, or
- a module/release checkpoint requires it.

---

## Core principle

> Validate locally during development. Validate globally at meaningful boundaries.

The purpose of this policy is to reduce agent time, token/tool consumption, repeated builds, and unnecessary CI work while preserving the full quality bar before module completion and release.
