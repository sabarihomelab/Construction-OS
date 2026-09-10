# Search and Indexing Engine

## Purpose

Construction OS provides global and module-level search without turning the search index into a second source of truth or a weaker authorization path.

PostgreSQL remains authoritative. Search data is a tenant-scoped, rebuildable projection of approved searchable fields.

## Core flow

```text
Business record commits
      ↓
search.index_entity durable job
      ↓
module search projection provider
      ↓
SearchDocument upsert
      ↓
PostgreSQL full-text index
      ↓
authorized query
      ↓
result identity/title hint
      ↓
normal authorized API loads current record
```

Indexing does not block the business save.

## Search projection contract

Each searchable business module owns a provider that returns an explicit `SearchProjection` containing only approved searchable content:

- entity type/id;
- entity version;
- title;
- optional subtitle;
- approved body/search text;
- approved keywords;
- required permission;
- optional scope type/id;
- internal route hint;
- source update timestamp.

Modules must not serialize entire ORM/database rows into search automatically.

Sensitive payroll, financial, personal, safety, legal or customer data is included only when the module contract explicitly allows it and assigns the correct permission/scope boundary.

## Tenant isolation

Every search document belongs to one organization. Global search always includes the current tenant as a server-side predicate.

There is no cross-tenant global index query exposed to company users.

## Permission and scope filtering

Search projection rows may declare:

```text
required_permission_key
scope_type
scope_id
```

A result is eligible only when the current user still has the required capability and, for scoped records, current access to that scope.

A search hit never grants access to the underlying record. Opening it always uses the ordinary authorized API.

If permissions change after indexing, current permission/scope evaluation controls the result; the index does not need to be rewritten merely because one user's role changed.

## Stale async jobs

Search indexing is asynchronous, so jobs can finish out of order.

Each projection may carry an entity version. An older indexing job must never overwrite a newer indexed version.

Deletion follows the same rule: a delayed delete for entity version 5 cannot remove a search projection that has already advanced to version 6.

## PostgreSQL first

Release 1 foundation starts with PostgreSQL full-text search and a GIN index.

The generated search vector weights:

- title highest;
- subtitle/keywords next;
- body lower.

The initial text-search configuration uses PostgreSQL's `simple` parser so one hardcoded English stemming configuration does not become a global product assumption. More language-aware tokenization/ranking can be layered later while preserving the projection interface.

An external search engine is not required merely because search exists. If data volume, typo tolerance, faceting or specialized drawing/document search later proves PostgreSQL insufficient, another implementation may be introduced behind the same domain contract.

## Query behavior

Search supports:

- tenant boundary;
- current permission filter;
- current scope filter;
- optional entity/module filter;
- ranked full-text results;
- bounded result counts.

Module-specific pages may add domain filters on top of their canonical business APIs/search projections.

## Indexing jobs

Current job types:

```text
search.index_entity
search.delete_entity
```

Job payloads contain entity identity/version, not record bodies.

The worker asks the registered module provider for the current approved projection. If the record no longer exists or is no longer searchable, the projection is removed safely.

## Rebuildability

Search is derived state. Construction OS must support rebuilding search projections from canonical records.

Operational recovery may therefore:

1. mark/rebuild one entity;
2. rebuild a project/module;
3. rebuild an entire tenant index.

Search corruption must never require editing business records.

## Files and drawings

The File/Media and Drawings processors may produce approved extracted text/metadata that specialized providers include in search.

Search never reads raw binary bytes directly during an interactive query.

Large document extraction is a background job. Until extraction completes, metadata search can still function and the UI may indicate processing/index freshness when useful.

## Realtime relationship

Indexing and realtime are separate:

```text
RFI saved
→ authoritative RFI event immediately
→ UI can refresh current RFI

search.index_entity runs asynchronously
→ global search catches up
```

The application does not delay a normal save until search indexing finishes.

## Performance

Release 1 performance testing will define budgets using representative tenant/project volumes.

The engine must use indexed predicates and bounded result sets. Search requests never trigger unbounded scans across all business tables or object storage.

## Operations

Admin/platform diagnostics should eventually expose privacy-safe information such as:

- index backlog;
- oldest pending indexing job;
- indexing failures by entity type;
- projection count by tenant/module;
- index freshness;
- rebuild status;
- average/p95 indexing duration.

## API activation rule

The underlying engine can be implemented before the public global-search endpoint is enabled.

A user-facing search endpoint must not be exposed until the session/access context can supply all required project/resource scopes. Defaulting scoped data to visible would be unsafe; silently hiding all project-scoped data would make global search incomplete and misleading.

## Release 1 remaining work

Before Release 1 is complete, Search also requires:

- complete project/resource scope resolution in Access Context;
- authenticated global-search API;
- command palette/global search UI;
- module-level search/filter UX;
- real providers for every Release 1 searchable business object;
- file/drawing/specification extraction integration;
- result navigation and state preservation;
- typo/fuzzy behavior decision based on usability testing;
- indexing/rebuild workers;
- operations metrics and rebuild controls;
- responsive/accessibility testing;
- representative-volume performance tests;
- cross-tenant and sensitive-data integration tests.
