# Drawings Module Contract

## Purpose

Drawings is a project-scoped construction drawing engine, not a generic PDF viewer. It owns sheet identity, controlled revisions, optimized render state, calibration, measurements, markups, pins and revision comparison while reusing File & Media for source/derived binary storage.

## Core objects

- `DrawingSet` — named collection of project sheets.
- `DrawingSheet` — stable sheet number/title/discipline identity.
- `DrawingRevision` — immutable source file/page plus processing and publish state.
- `DrawingRenderPackage` — derived render manifest for browser/mobile/offline use.
- `DrawingCalibration` — versioned real-world scale definition.
- `DrawingMarkup` — versioned/soft-retired markup geometry and style.
- `DrawingMeasurement` — authoritative server-calculated length/area/volume/count.
- `DrawingPin` — normalized location linked to RFI/photo/punch/inspection/submittal or another permitted object.
- `DrawingComparison` — durable revision-overlay/comparison result.

## Backend processing engine

Large drawing work never blocks the normal HTTP request path. A revision queues `drawings.process_revision`; a configured renderer adapter reads the private source, normalizes it, creates optimized render/tile/preview assets and returns a versioned manifest. Revision comparison is also a durable job.

The renderer is provider-independent so managed SaaS, dedicated and self-hosted deployments can use different open-source/private rendering implementations without changing drawing business data.

## Client rendering

The browser/PWA should render from optimized packages, load only useful visible detail, and keep pan/zoom/markup interaction responsive. The client must not repeatedly download the full original drawing merely to zoom or add a markup.

## Measurement engine

Calibration defines the conversion between drawing coordinates and a real-world unit. Length/area/volume/count are computed by the backend from stored geometry; the server does not trust a browser-supplied final measurement value. Calculations use Decimal arithmetic for reproducibility.

Takeoff will reuse this same geometry/measurement foundation so there is one authoritative interpretation of drawing quantities.

## Markups and collaboration

Markups use optimistic versions. Concurrent/stale edits conflict rather than silently overwriting another user's work. Retiring a markup is a soft historical action. Realtime events carry identifiers/revisions, not entire drawing contents.

## Revision control

A revision moves through draft/processing/ready/published/superseded/failed states. Only a render-ready revision can be published. Publishing supersedes the previous published revision without deleting it.

Revision comparison requires two revisions of the same sheet and produces a derived, rebuildable comparison/overlay result.

## Pins

Pins store normalized coordinates from 0 to 1 so links survive device resolution changes. Business targets remain references, allowing RFIs, photos, punch items, inspections and submittals to maintain their own authoritative data.

## Authorization

Capabilities:

- `drawings.drawing.view`
- `drawings.drawing.revise`
- `drawings.drawing.publish`
- `drawings.markup.manage`
- `drawings.measurement.manage`
- `drawings.comparison.run`
- `drawings.drawing.manage`

Every action is additionally bounded by current project scope.

## Offline and performance

Release 1 requires downloadable authorized drawing packages, visible offline/sync state, field markups where permitted, reconnect synchronization, conflict handling and no silent data loss. Render manifests should support progressive/level-of-detail loading so large drawing sets remain usable on field devices.

## Remaining implementation before Release 1

The current foundation defines persistence, processing contracts, durable jobs and measurement logic. Release 1 still requires an actual renderer/storage-worker adapter, secure derived-asset delivery, browser/PWA drawing canvas, markup/measurement APIs, offline drawing packages, revision overlay UI, production performance testing and domain-level integration with RFIs/Takeoff/Punch/Inspections.

The feature remains `planned` and hidden until those user-facing requirements are genuinely usable.
