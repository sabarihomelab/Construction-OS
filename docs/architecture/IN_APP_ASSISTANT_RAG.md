# Construction OS Assistant — In-App RAG Architecture

## Purpose

Construction OS Assistant is an optional in-app support layer. Its first responsibility is to help operators and administrators understand the product they actually have installed.

Initial supported intent areas:

- product help and feature explanation;
- India-first terminology/workflow guidance from shipped product documentation;
- company configuration explanation from permission-visible knowledge;
- installed module and environment explanation;
- release-note and upgrade-readiness guidance;
- migration/backup/rollback procedure explanation;
- future user guidance tied to the current page/task.

This is deliberately narrower than an autonomous construction agent.

## Authority boundary

The Assistant is **never** the source of truth for:

- measurement;
- certification;
- RA billing;
- GST/TDS/withholding calculations;
- payment;
- budget posting;
- approvals;
- safety closure;
- database migration execution;
- version rollback execution;
- permission changes;
- configuration changes.

The Assistant may explain or propose. Deterministic domain services and explicitly authorized users execute authoritative actions.

## Retrieval sources

The Assistant composes evidence from two separate source families.

### Product knowledge

App-owned, release-versioned sources such as:

- India-first product contract;
- module contracts;
- release notes;
- installation lifecycle;
- deployment composition;
- migration/upgrade notes;
- configuration guidance;
- help topics.

Product knowledge is shipped with the release and is not customer-editable.

### Tenant/company knowledge

Reuse the existing `TenantKnowledgeSource` / `TenantKnowledgeChunk` store. Sources remain organization-scoped, permission-scoped and project/scope-aware.

Examples:

- customer procedures;
- configured templates/instructions;
- approved company manuals;
- selected project knowledge;
- controlled configuration explanations.

Do not create a second tenant RAG database.

## Request flow

`User question → authenticated session → authorization/project scope → intent classification → retrieve product evidence → retrieve permitted tenant evidence → bounded context assembly → provider call → evidence-linked answer`

The model never receives unrestricted database access.

## Evidence rules

Every response must return evidence/source labels. The model instruction must require:

- use only supplied evidence for factual product/environment claims;
- distinguish product documentation from tenant/company knowledge;
- say when evidence is insufficient;
- never claim an upgrade/migration/configuration action was executed;
- never invent current statutory tax/withholding rules;
- never infer permissions from UI visibility alone.

## Upgrade and rollover advisor

Upgrade assistance combines RAG with structured local state. Relevant non-secret state may include:

- installed Construction OS version;
- target release/version knowledge;
- installation path identifier;
- deployment profile;
- database mode/endpoint summary;
- storage provider;
- installed runtime modules;
- worker profiles;
- current migration revision;
- latest verified backup reference;
- configuration-health/operations status.

Example questions:

- "What changed in this release?"
- "Can I add Procurement without installing Drawings?"
- "What should be backed up before this upgrade?"
- "Why is upgrade readiness blocked?"
- "What modules were added since our current version?"
- "How do I recover if the migration fails?"

The Assistant explains the plan. `setup.ps1` / the future signed updater performs the controlled operation.

## Provider model

Assistant inference is provider-pluggable. Supported architecture modes are:

- `disabled`;
- local/on-prem model such as Ollama-compatible inference;
- approved OpenAI-compatible cloud/private endpoint.

Provider credentials are deployment secrets and must not enter source control, audit payloads, model context or tenant knowledge indexes.

Cloud use must be explicit. Deployments that require data to remain on-premises can select a local provider. Core Construction OS workflows must continue to work with AI disabled.

## Cost and performance

The Assistant must not load all company/project data for every query.

Use:

- page/intent-scoped retrieval;
- permission-scoped tenant chunks;
- bounded top-k evidence;
- capped context sizes;
- module/release metadata rather than full database dumps;
- cached product indexes by release version;
- optional embeddings/vector retrieval later;
- lexical/structured retrieval as a valid fallback.

AI workers/providers may be deployed separately when resource requirements justify it. Normal business modules must not depend on the AI runtime.

## Privacy and logging

Do not persist raw prompts/responses by default merely for analytics. Audit high-level assistant usage metadata where required, such as actor, mode, provider, evidence source count and outcome, while excluding secrets and minimizing customer content.

A future explicit organization setting may control retention of conversational history.

## Future construction intelligence

After authoritative India project data exists, the same evidence framework may support questions such as:

- why a project is over budget;
- BOQ items with excess material consumption;
- low crew productivity;
- completed but unbilled work;
- billed but unreceived amounts;
- pending subcontractor certifications;
- material shortages affecting work;
- delayed activities;
- multi-project daily summaries.

These answers must trace back to authoritative transactions and remain advisory.
