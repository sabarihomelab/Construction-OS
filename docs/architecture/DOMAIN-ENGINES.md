# Construction OS Domain Engines

Construction OS is not a collection of forms over database tables. Modules that require calculations, geometry, scheduling, synchronization, document processing, financial posting or other complex behavior own explicit domain engines.

## Design rule

The authoritative rule is:

```text
UI interaction
   ↓
API/domain command
   ↓
Authorization + validation
   ↓
Domain engine
   ↓
Transactional state
   ↓
Outbox/jobs/projections as needed
   ↓
Realtime client update
```

The browser may perform local previews and optimistic interactions, but authoritative business meaning is enforced by the backend/domain layer.

## Estimating and Takeoff Engine

The Estimating engine will own:

- estimate versions and comparison;
- estimate hierarchy/work breakdown;
- quantity, unit cost and extended cost calculations;
- labor/material/equipment/subcontract resources;
- assemblies and reusable templates;
- productivity, waste and yield factors;
- markups, overhead, profit, taxes/allowances where configured;
- alternates and exclusions;
- cost-code mapping;
- formula parsing/evaluation;
- deterministic rounding/precision rules;
- recalculation dependency graph;
- import/export mappings;
- audit/version history;
- evidence links back to takeoff/drawing/specification sources.

Large recalculations run as durable jobs. Small edits may calculate an immediate preview in the UI, but the server returns the authoritative result.

Takeoff will own geometry-derived quantities such as count, length, area and volume. Drawing calibration/revision identity must be preserved so a quantity can always be traced to the exact drawing revision and geometry used.

## Drawing Processing and Rendering Engine

Drawing support is split deliberately between backend processing and client rendering.

### Backend responsibilities

- ingest original PDF/drawing source;
- identify pages/sheets;
- preserve original/revision identity;
- extract metadata/text where supported;
- generate optimized sheet representations;
- generate thumbnails/previews;
- generate tile pyramids or other level-of-detail assets when appropriate;
- compute/store page geometry and dimensions;
- prepare revision comparison/overlay inputs;
- produce offline drawing packages;
- run expensive conversions in background jobs;
- never mutate an old drawing revision in place.

### Client responsibilities

- smooth pan/zoom;
- render only visible regions/levels of detail;
- markup interaction;
- measurement interaction;
- selection/snapping where supported;
- RFI/photo/punch/inspection pins;
- local/offline cache;
- responsive touch/keyboard/mouse controls.

Markup/measurement/pin data remains structured and separate from the immutable original drawing bytes. Adding an RFI pin must not create another full PDF copy.

## Scheduling Engine

Scheduling will own:

- activities and milestones;
- dependencies and relationship types;
- working calendars;
- constraints;
- durations;
- early/late dates;
- total/free float;
- critical path calculations;
- baselines;
- look-ahead windows;
- actual progress;
- delays;
- schedule revisions/versioning;
- linkage to submittals, procurement, RFIs and field progress.

The field experience remains simple even though the schedule engine is capable of deeper calculations.

## Workflow and Approval Engine

Workflow is not hardcoded separately in each module. The shared workflow engine will own:

- versioned workflow definitions;
- states/transitions;
- transition permissions;
- conditional routing;
- assignments/ball-in-court;
- due dates;
- reminders/escalations;
- approvals/rejections;
- reopen/withdraw rules;
- step-up authentication requirements;
- historical workflow version preservation.

RFI, Submittal, Change, Invoice, Time, Safety and other modules consume it with domain-specific validation layered on top.

## Financial and Job Cost Engine

Financial modules will use deterministic backend posting/calculation services for:

- budget calculations;
- commitments and purchase orders;
- change impacts;
- progress billing;
- retainage;
- AP/AR;
- job-cost allocation;
- payroll cost allocation;
- journal/GL posting;
- currency conversion snapshots;
- accounting periods;
- historical calculation versions;
- reconciliation and balancing checks.

Posted historical financial records are never silently recalculated because a current configuration, exchange rate or rule changed.

## Realtime and Offline Sync Engine

The sync engine owns:

- client/device identity;
- durable offline mutation identities;
- idempotency;
- entity versions;
- retry;
- conflict detection;
- deterministic/human conflict resolution;
- acknowledgement;
- reconnect/catch-up;
- realtime invalidation events.

Offline/realtime behavior must not be independently reinvented in Daily Reports, Time, RFIs, Drawings, etc.

## Search and Indexing Engine

Search will own tenant-scoped, rebuildable search projections for supported objects, including:

- global search;
- module search;
- filters/facets;
- drawing/document text where extraction is supported;
- incremental indexing from committed events/jobs;
- permission-aware result filtering;
- index freshness/health.

The search index is derived state, never authoritative business truth.

## Reporting and Analytics Engine

Reporting will own:

- reporting projections;
- saved views;
- filters/grouping;
- calculated reporting fields;
- drilldowns;
- charts/dashboards;
- scheduled reports;
- PDF/Excel/CSV generation;
- historical timezone/currency semantics;
- large report jobs.

Heavy analytical queries must not repeatedly scan transactional tables on normal dashboard requests.

## Document/File Processing Engine

File processing owns:

- malware scanning;
- actual type detection;
- metadata extraction;
- preview/thumbnail generation;
- PDF/image optimization;
- derivative lifecycle;
- quarantine/failure states;
- checksum verification;
- storage-provider abstraction.

Specialized modules such as Drawings may add additional processors without bypassing the shared file security/lifecycle model.

## Integration and Mapping Engine

External connectors use the Integration/Ingestion/Mapping/Reconciliation services for:

- authentication references;
- raw ingestion;
- validation/staging;
- versioned mappings;
- transformations;
- deduplication;
- idempotency;
- conflict policy;
- reconciliation;
- retry;
- traceability.

External systems never write directly to canonical Construction OS tables.

## AI/Intelligence Engine

AI is an optional assistance layer, not a source of authoritative business state.

It may support:

- document/drawing extraction;
- scope gap suggestions;
- summaries;
- drafting;
- semantic search;
- risk highlighting;
- plain-language operational/help explanations.

It does not silently approve, post, certify or make authoritative financial, contractual or safety decisions. Evidence/source links are preserved where the use case depends on extracted facts.

## Engine contract

Each engine/module must document:

- authoritative inputs/outputs;
- versioning rules;
- deterministic vs advisory behavior;
- synchronous vs job-based operations;
- idempotency;
- retry/recovery;
- permissions;
- audit events;
- realtime events;
- offline behavior where relevant;
- performance budgets;
- historical-data behavior;
- observability;
- tests.

Release 1 must contain production-usable implementations of the engines required by its business capabilities. A page shell or CRUD endpoint does not satisfy an engine requirement.
