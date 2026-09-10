# Documents & Specifications Module Contract

## Purpose

Documents & Specifications provides project-scoped document control on top of the shared File & Media service. It owns the business identity, revision history and issued state of a document; it does not duplicate binary file storage.

## Core objects

- `DocumentFolder` — project folder hierarchy.
- `Document` — stable managed document identity and metadata.
- `DocumentRevision` — immutable source-file reference plus controlled issue/publish state.
- `SpecificationSection` — structured specification section metadata linked to a specification document.

## Storage boundary

File bytes remain in File & Media. A document revision references an immutable `FileVersion`. A published document revision may only reference a file version that has completed processing and has a clean malware-scan state.

This separation allows the same secure file/storage service to support documents, drawings, RFIs, submittals, bids, photos and closeout without treating a file upload as a controlled construction document.

## Revision behavior

Documents have a stable project-level number and monotonic version. Revisions have a sequence and user-visible revision label. Publishing a new revision supersedes the previous published revision rather than replacing or deleting it.

Historical references should prefer the exact `DocumentRevision` where business meaning depends on what was issued at that time.

## Specifications

Specification documents may expose structured sections with section number, title, division code and page range. Section identity is stable within the document. The section model is intended to support RFI/Submittal/Estimating references without copying specification text into those modules.

## Authorization

Capabilities:

- `documents.document.view`
- `documents.document.create`
- `documents.document.publish`
- `documents.document.manage`

All document access is bounded by the current organization and project scope. A project-scoped role does not gain access to documents in another project.

## Realtime and Search

Document create/publish operations emit minimal project-scoped realtime events. Search uses an approved projection containing document number/title/type/discipline/description and project scope. Search is not a second authorization path; opening a result still uses the normal authorized business API.

## Offline

Release 1 should support authorized offline reference packages for project documents/specifications needed in the field. Offline copies must retain document/revision identity, sync status and expiry/revocation behavior. Creating or publishing controlled revisions remains an online/high-integrity workflow unless explicitly supported by a future module contract.

## History and deletion

Published revisions are not overwritten. Archival does not erase issued history. Destructive lifecycle actions are governed through Data Governance and legal-hold/financial/contractual restrictions.

## Release 1 acceptance

Release 1 requires secure upload/download integration, responsive document navigation, revision history, publish/supersede flow, specification sections, project-scoped search, offline field availability where selected, export/closeout integration, audit, realtime invalidation, and tests. The feature remains hidden while its user-facing workflow is incomplete.
