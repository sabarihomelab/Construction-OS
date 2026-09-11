# Construction OS Android App — Work Instruction

## 1. Objective

Build the Android client for Construction OS inside the existing monorepo. Android is the only mobile target for this phase. Do not build iOS and do not create another repository.

The app must feel like a polished native consumer app rather than a web page inside a phone:

- immediate UI response to taps;
- local-first reads and field data entry;
- background synchronization;
- smooth scrolling on ordinary Android phones;
- low memory/network usage;
- resilient behavior on weak or unavailable site connectivity;
- server-authoritative permissions, approvals, money, certification, history and project/tenant isolation.

The app must be usable on normal 8 GB RAM / 64 GB storage Android phones without loading entire projects into memory.

## 2. Repository and branch rules

Repository:

`Construction-OS/`

Work only on:

`build/platform-foundation`

Do not create feature branches unless the user explicitly changes this instruction.

Create the Android application under:

`apps/mobile/`

Expected top-level product layout:

```text
Construction-OS/
├── apps/
│   ├── api/
│   ├── web/
│   └── mobile/
├── docs/
├── docker-compose.yml
└── ...
```

`main` remains the stable/promotion branch. Do not push active development directly to `main`.

## 3. Current backend baseline

The current cumulative backend/frontend-development branch is `build/platform-foundation`.

Modules currently ready for client integration:

1. Company / Party
2. WBS / Cost Codes
3. BOQ
4. Estimate / Rate Analysis / Budget
5. Workforce / Contract Labour / Attendance
6. DPR / Reporting

The backend also already contains broader foundations for Projects, Files, Workflow, Jobs, Search, Offline Sync, Equipment/Materials, Procurement, Safety, Scheduling, Subcontracts and Financials. Do not expose a planned feature merely because its backend folder exists. Use the server Feature Registry and access context.

Existing client integration contract:

`docs/product/FRONTEND-INTEGRATION-MODULES-1-6.md`

Read that file before implementing module screens.

## 4. Android technology decision

Use native Android.

Required foundation:

- Kotlin
- Jetpack Compose
- Material 3
- Navigation Compose
- Kotlin Coroutines + Flow
- ViewModel
- Room for structured local data/cache
- WorkManager for durable background sync/uploads
- OkHttp + Retrofit for REST transport
- Kotlin serialization or Moshi for JSON; choose one and use it consistently
- Android Keystore for secrets/session material
- DataStore only for small preferences/settings, never as the main business database
- CameraX only when camera behavior needs more control than the normal capture intent

Use current stable dependency versions through a Gradle version catalog. Do not paste stale dependency versions throughout individual Gradle files.

Recommended minimum SDK: 26 unless an existing repository requirement forces another value. Compile/target against the latest stable SDK installed in CI/Android Studio.

Application/package identity for development may start as:

`com.constructionos.app`

Treat changing the application ID as a release decision before public distribution.

## 5. Core architecture

The mobile app is local-first, not network-first.

```text
Jetpack Compose UI
        ↓
ViewModel / UI State
        ↓
Domain use cases
        ↓
Repository
   ↙           ↘
Room DB       Remote API
   ↑             ↓
   └── Sync / WorkManager ──┘
```

### Rule: Room is the UI read source for field workflows

For field-friendly workflows, screens observe Room using Flow. A tap updates local state immediately. Network synchronization happens separately.

Do not build ordinary field screens like:

`Tap -> spinner -> API -> wait -> update UI`

Preferred flow:

`Tap -> local update immediately -> mutation queued -> background sync -> server validates -> synced/conflict state`

Server-only actions remain server-only, for example:

- final approval;
- certification;
- financial posting;
- budget approval;
- sensitive access/role changes;
- tax/withholding decisions.

Those may display progress because central authority is required.

## 6. Backend fitting required before Android integration

Do not rewrite the backend. Add a small mobile transport/readiness layer to the existing session/offline architecture.

### 6.1 Native authentication transport

Current backend requests are browser-oriented: active sessions are read from a session cookie and mutations use CSRF.

The Android client must not be forced to emulate browser cookie/CSRF behavior.

Implement native session support using the existing `Session`, authentication provider and authorization foundations.

Required behavior:

- accept `Authorization: Bearer <session token>` for native API requests;
- retain cookie + CSRF behavior for the web app;
- CSRF is required for cookie-authenticated unsafe requests, not for bearer-authenticated native requests;
- use the existing session expiry, revocation, membership and user validation logic;
- never store raw tokens in the database;
- never create a second permission system for Android.

### 6.2 Login/session creation

The repository already has authentication-provider abstractions and session issuance services but no mounted production login router.

Create a provider-neutral mobile authentication API rather than hardcoding permanent username/password logic into domain code.

Development may use a clearly development-only login provider/flow for local testing. It must be impossible to enable accidentally in production.

Production direction is OIDC/OAuth Authorization Code + PKCE or another approved identity provider, feeding the existing authentication assertion/session service.

Do not invent a home-grown production password database merely to make the first Android screen work.

The mobile login result must allow the user to select an organization membership if more than one is available and then obtain an active session for that membership.

### 6.3 Session/access context

After authentication call:

`GET /api/v1/session/context`

Treat it as the navigation/authorization authority.

It already exposes:

- `organization_id`
- `membership_id`
- `authorization_revision`
- `configuration_revision`
- organization permissions
- scopes
- project permissions
- visible features
- `mobile_enabled`
- `offline_enabled`

The app must not infer access from job title or a locally stored role name.

### 6.4 Offline API extension

Existing backend already supports device registration, device sync state, mutation receipts/conflicts at service level, and event acknowledgement.

Complete domain-specific offline mutation APIs gradually for the first mobile workflows:

1. Attendance
2. DPR work progress / notes / delays
3. DPR photo metadata/uploads
4. Equipment usage when that feature is released
5. Material receipts/consumption when that feature is released
6. Safety/inspection when that feature is released

Every queued mutation requires:

- stable client mutation UUID;
- device ID;
- entity ID where known;
- operation type;
- base revision/version where governed;
- deterministic request hash/idempotency;
- server result or explicit conflict/rejection.

Never silently discard a mutation.

## 7. Security model

Assume the APK, local database and UI can be inspected or modified on a hostile/rooted device.

Therefore:

- the Android app is never the authority for permissions;
- the Android app is never the authority for project/company identity;
- never trust prices, totals, approval status, tax, rates, certifications or permissions simply because the client sends them;
- server recalculates/validates authoritative results;
- server enforces tenant/project scope on every resource;
- server enforces current revision/state transitions;
- server controls approval/certification/posting;
- keep server secrets, database credentials, signing secrets and third-party private keys out of `apps/mobile`;
- use HTTPS outside local development;
- store session/refresh credentials using Android Keystore-backed secure storage;
- do not log tokens, authorization headers, PAN/GST/private commercial data or sensitive payloads in release logs;
- redact sensitive crash telemetry;
- use Play Integrity before production/pilot hardening for sensitive operations;
- treat integrity signals as an additional signal, not a replacement for server authorization.

Sensitive data caching policy must be explicit. Attendance and normal field data may be cached for offline work. Sensitive commercial/financial information should not be downloaded/cached unless the user has permission and the use case requires it.

## 8. Android runtime permission policy

Do not request a pile of Android permissions on first launch.

Request only when the feature is used.

### Initially required

Internet/network access is declared in the manifest and does not require a runtime prompt.

### Camera

Request camera access only when the user selects `Take Photo`.

### Existing photos/files

Prefer Android Photo Picker / Storage Access Framework so broad storage permissions are not required.

### Location

Do not request location globally.

Request foreground location only for report types/workflows whose capability/configuration explicitly requires a location stamp. If DPR location is optional and disabled for the project, never request it.

Do not add background location unless a later approved business requirement genuinely needs continuous tracking.

### Notifications

On Android versions requiring notification runtime permission, request it contextually after explaining the value (approvals, sync failures, report ready, assignments), not immediately on first launch.

### Biometric

Biometric unlock may later protect reopening an already authenticated local session. It does not replace server authentication.

## 9. Performance rules — game-like responsiveness

Target the perception of a high-quality native app.

Performance goals:

- tap feedback: immediate, preferably under 100 ms;
- cached screen navigation: effectively immediate;
- scrolling target: 60 FPS on ordinary mid-range devices;
- no network call on the UI thread;
- no database work on the UI thread;
- no full-resolution image decoding for thumbnails;
- no loading entire BOQ/workforce/project history into memory;
- use lazy lists with stable keys;
- use paging for large datasets;
- keep recomposition scopes small;
- use immutable/stable UI models where practical;
- use thumbnails for image grids;
- upload photos in background;
- heavy reporting/Excel/PDF/AI remains server-side;
- measure performance; do not assume it.

Add Baseline Profiles/macrobenchmark work after the main navigation and key workflows stabilize.

## 10. Local data strategy

Room should store only the current/recent working set, not a copy of the entire server.

Initial local entities should include approximately:

- current user/session metadata (no raw token in Room);
- access context snapshot;
- projects assigned to the user;
- active project summary;
- active worker assignments needed for attendance;
- attendance registers/entries;
- WBS subset needed by active workflows;
- approved BOQ lookup subset needed for DPR/work progress;
- DPR drafts and DPR-owned editable sections;
- pending mutations;
- sync state/conflicts;
- file/photo upload queue metadata;
- lightweight cached thumbnails metadata.

Keep credentials in secure storage, not Room.

Use DataStore for preferences such as:

- selected project ID;
- theme;
- compact/comfortable UI preference;
- last successful sync timestamp for presentation only.

Server/device sync state remains authoritative for synchronization.

## 11. Sync state visible to the user

Every locally editable field workflow needs a clear but unobtrusive state:

- `Saved on device`
- `Waiting for network`
- `Syncing`
- `Synced`
- `Needs attention`

Do not block normal field entry just because the network disappears.

Conflict behavior:

- preserve the user’s local edit;
- preserve the server version;
- display a clear conflict screen where automatic reconciliation is unsafe;
- never overwrite an approved/newer server revision silently.

## 12. Image/photo architecture

Photos are one of the largest mobile performance risks.

Required flow:

```text
Capture/select
  ↓
Create app-private working copy
  ↓
Create thumbnail
  ↓
Show thumbnail immediately
  ↓
Queue upload
  ↓
Upload in WorkManager when permitted
  ↓
Server FileAsset/FileVersion
  ↓
Attach to business entity
```

Requirements:

- never render a multi-megabyte original in a list;
- preserve original if the business/audit policy requires it;
- generate practical upload variants/thumbnails;
- expose progress/retry/cancel where safe;
- upload idempotently;
- retain local file until server acknowledgement;
- clean up acknowledged local temp files according to cache policy;
- metadata such as location/time must be explicit and not silently fabricated.

## 13. Application navigation

### App startup

1. Splash/bootstrap
2. Load encrypted session material
3. If no valid session -> Login
4. If session exists -> validate/refresh session
5. Fetch `/session/context`
6. Sync assigned projects/minimum bootstrap dataset
7. Open last allowed project or Project Selector

### Primary navigation

Use a field-first bottom navigation rather than exposing every ERP module.

Initial suggested bottom destinations:

- Home
- Field
- Workforce
- Projects/More

Actual visibility is permission/feature driven.

Do not show a disabled admin/commercial feature merely because a Composable exists.

### Project context

Most working screens operate inside one active project.

Display the active project clearly and allow switching when the user has access to multiple projects.

Changing active project must:

- preserve unsynced mutations from the previous project;
- change local query scope;
- never mix cached project data;
- kick off a lightweight sync for the newly selected project.

## 14. Initial screen set

### 14.1 Splash / bootstrap

Display brand mark and minimal progress state.

Tasks:

- secure session restore;
- DB open/migration;
- context refresh;
- minimal sync.

Do not block for full project sync.

### 14.2 Login

Simple, professional Construction OS login.

For development, bind to the approved dev authentication flow. Keep UI abstraction ready for production IdP/PKCE.

States:

- idle;
- authenticating;
- membership selection if needed;
- success;
- invalid credentials/provider result;
- offline with no existing session;
- server unavailable.

### 14.3 Project selector

Show only projects returned/allowed by backend project access.

Card content:

- project name/code;
- location if available;
- status;
- sync freshness;
- optional client name.

Support search when project count grows.

### 14.4 Project Home / Today

This is the key supervisor landing screen.

Prioritize actions rather than ERP modules:

- Attendance
- Update Work
- DPR
- Add Photo
- Material Received (when released)
- Material Used (when released)
- Equipment (when released)
- Report Issue / Safety (when released)

Also show:

- date/shift;
- synchronization indicator;
- today’s attendance summary;
- DPR status;
- pending uploads;
- actions needing attention.

### 14.5 Workforce / workers

Initial mobile scope:

- worker lookup;
- crew lookup;
- project assignment visibility;
- attendance entry.

Do not expose worker commercial rates unless a future mobile screen has the explicit rate permission and use case.

### 14.6 Attendance

This is the first major mobile workflow.

Requirements:

- today/project/shift register;
- populate active project workers;
- fast mark all present;
- fast per-worker Present / Absent / Half Day / Leave / Weekly Off;
- regular/OT hours;
- optional WBS assignment;
- crew/trade/employer filters;
- search;
- bulk operations;
- local-first editing;
- visible sync state;
- submit/review/approve based on permissions and server workflow state;
- approved register is read-only except server-supported controlled actions.

The screen must handle hundreds of workers smoothly with LazyColumn/Paging and stable item keys.

### 14.7 DPR

DPR mobile UI should assemble authoritative information rather than asking the supervisor to retype it.

Sections:

- report date/shift;
- weather/basic header if configured;
- attendance summary (read from approved attendance);
- work progress entry;
- WBS/approved BOQ selection;
- delays/blockers;
- notes;
- materials received/used summaries when corresponding modules are released;
- equipment summary when released;
- safety summary when released;
- photos;
- configured custom fields;
- submit/review/approve actions.

After approval:

- display report generation state from `/report-generation`;
- do not block UI waiting for PDF;
- when issued, show filename and Download/Open action;
- historical issued report remains immutable.

### 14.8 Party Directory

Mobile scope for Modules 1–6:

- search/list Parties;
- basic details/contact;
- party type;
- project relationship where relevant.

Create/edit may be hidden from normal field users based on permissions.

### 14.9 WBS lookup

Mobile WBS is primarily a fast selector/viewer for field workflows.

Use searchable hierarchical presentation.

Avoid making supervisors navigate a huge tree every time; show recent/favorites/current-location WBS later if needed.

Full structural administration can remain web/admin oriented even though APIs exist.

### 14.10 BOQ lookup

For field/mobile initially:

- approved BOQ lookup;
- item search;
- quantity/unit/rate visibility only according to permission/product decisions;
- select BOQ item for work progress where allowed.

Full import/approval administration can remain web-first initially.

### 14.11 Estimating / Budget

Treat as a permission-sensitive management screen, not a primary field tab.

Initial mobile scope can be read/review/approval-oriented after core field UX is stable. Do not prioritize complex rate-analysis data entry before Attendance/DPR.

### 14.12 Company Settings / admin

Do not place company administration in normal bottom navigation.

Expose under More/Admin only when visible feature and permission allow it.

High-risk configuration should remain web-first unless there is a proven mobile need.

## 15. Permission-driven UI rules

After `/session/context`:

- store permission sets in memory and a cache snapshot;
- show feature only if returned as visible and `mobile_enabled=true`;
- project action checks use the selected project’s permission set;
- organization action checks use organization permissions;
- hiding a button is UX only; backend enforcement remains mandatory;
- when authorization revision changes, refresh access context;
- a server 403 invalidates assumptions and should trigger context refresh before displaying the final denial.

Never use strings such as `role == "Admin"` as the source of truth for UI authorization.

## 16. Error handling contract

Map API responses consistently:

- 401 -> session expired / reauthenticate;
- 403 -> permission denied; refresh context where appropriate;
- 404 -> record no longer visible/found;
- 409 -> stale revision/conflict; preserve local edit and reconcile;
- 422 -> display actionable validation/business-rule message;
- 429 -> retry later with backoff;
- 5xx/network failure -> keep safe local mutation queued where operation is offline-capable.

Do not show raw server traces/exceptions to users.

## 17. Recommended code organization

```text
apps/mobile/
├── app/
│   └── src/main/java/com/constructionos/app/
│       ├── ConstructionOsApp.kt
│       ├── MainActivity.kt
│       ├── core/
│       │   ├── auth/
│       │   ├── database/
│       │   ├── network/
│       │   ├── sync/
│       │   ├── files/
│       │   ├── permissions/
│       │   ├── navigation/
│       │   ├── design/
│       │   └── util/
│       ├── feature/
│       │   ├── bootstrap/
│       │   ├── login/
│       │   ├── projects/
│       │   ├── home/
│       │   ├── workforce/
│       │   ├── attendance/
│       │   ├── dpr/
│       │   ├── parties/
│       │   ├── wbs/
│       │   ├── boq/
│       │   ├── estimating/
│       │   └── admin/
│       └── data/
│           ├── local/
│           ├── remote/
│           └── repository/
├── build.gradle.kts
└── ...
```

Avoid a giant `utils` package and avoid putting business rules inside Composables.

## 18. UI design system

Build a small Construction OS mobile design system before duplicating styles across screens.

Create reusable components for:

- app bars;
- project switcher;
- primary action cards;
- status chips;
- sync-state badge;
- offline banner;
- large field action button;
- search field;
- filter chips;
- list rows;
- empty/error/loading states;
- approval action bar;
- numeric/unit input;
- WBS/BOQ selector sheet;
- worker attendance row;
- photo tile/upload state;
- confirmation sheet.

Field UX rules:

- large touch targets;
- one-handed operation where practical;
- minimal typing;
- numeric keyboard for quantities/hours;
- carry forward/recent selections;
- visible project/date context;
- no tiny spreadsheet-style controls for field entry;
- dark/light theme supported, but functionality first.

## 19. Development/test environment

Android development/testing can be done without Play Store publication.

Required local tools:

- Android Studio
- Android SDK/emulator
- JDK required by current Android Gradle Plugin
- existing Docker/API environment
- physical Android phone optional but strongly recommended

Testing against local backend:

- Android emulator may access host services through `10.0.2.2`;
- a USB-connected physical Android device may use `adb reverse` for a local API port, or use the development machine LAN address;
- never use production secrets for local development.

Build types:

- `debug`: local/dev endpoints, verbose developer diagnostics, no production distribution;
- `release`: no debug provider, no sensitive logs, minification/optimization configured after stability;
- optionally `staging` later.

## 20. Testing requirements

### Unit tests

- reducers/ViewModels;
- permission decisions;
- local mutation state transitions;
- sync retry/backoff decisions;
- DTO/domain/entity mapping;
- conflict mapping.

### Room tests

- migrations;
- project isolation;
- pending mutation persistence;
- cache replacement/upsert behavior.

### API integration tests

- mobile bearer session;
- session expiry/revocation;
- `/session/context`;
- project permission enforcement;
- Attendance lifecycle;
- DPR lifecycle/report-generation;
- offline device registration;
- idempotent mutation replay;
- stale revision conflict.

### UI tests

At minimum:

- login -> project selector;
- project home;
- offline attendance entry;
- reconnect/sync;
- attendance submit;
- DPR work progress/photo entry;
- DPR submit/approval visibility based on permissions;
- generated report ready/download state.

### Performance tests

Test with realistic data, not ten demo rows:

- hundreds of workers;
- thousands of WBS/BOQ lookup rows;
- many DPR photos;
- weak network;
- offline/reconnect cycles.

Measure startup, frame timing, memory and list performance.

## 21. CI integration

Do not break the existing API/web CI.

Once the Android skeleton compiles locally, extend CI with an Android job that at minimum performs:

- Gradle dependency resolution;
- lint;
- unit tests;
- debug assemble;
- later instrumentation tests where practical.

Keep Android CI independent enough that failures clearly identify mobile vs API/web.

## 22. Implementation sequence

### Phase A — Mobile backend fit

1. Read current session/authentication/offline code.
2. Add bearer-session support without breaking cookie sessions.
3. Add native login/session-creation transport around the existing authentication provider architecture.
4. Add membership selection if required.
5. Confirm `/session/context` works with native bearer auth.
6. Adapt CSRF dependency so bearer clients are not forced to send browser CSRF tokens.
7. Add tests for cookie + bearer behavior.
8. Confirm current API/web/live-stack CI remains green.

### Phase B — Android foundation

1. Create `apps/mobile` native Compose project.
2. Add version catalog/dependencies.
3. Add design system/theme.
4. Add network client.
5. Add secure session store.
6. Add Room DB.
7. Add repositories/use cases.
8. Add WorkManager sync foundation.
9. Add navigation shell.
10. Add centralized API/error mapping.
11. Add Android CI job.

### Phase C — Login and bootstrap

1. Splash.
2. Login.
3. Membership selection if required.
4. Session restore/logout.
5. Access-context load.
6. Device registration.
7. Project bootstrap/cache.
8. Project selector.

Do not proceed to deep business screens until this path works reliably on an emulator and physical phone.

### Phase D — Project Home

Build the field-first Today screen and permission-driven navigation.

It should already feel polished before implementing every module.

### Phase E — Attendance

Implement complete Attendance workflow as the first offline-first business feature.

Acceptance test:

- open project;
- create/open today’s register;
- mark 35+ workers quickly;
- go offline;
- continue editing;
- close/reopen app;
- data remains;
- reconnect;
- sync once without duplicates;
- submit;
- permissions/state rules respected.

### Phase F — DPR

Implement mobile DPR on top of authoritative Attendance and existing DPR provider.

Acceptance test:

- open/create DPR;
- enter WBS/BOQ-linked progress;
- add notes/delay/photo;
- work offline where supported;
- sync;
- submit;
- approver approves if configured;
- generation status updates asynchronously;
- issued PDF can be opened/downloaded.

### Phase G — Supporting Modules 1–4

Add Party/WBS/BOQ/Estimating mobile views according to real mobile need and permissions.

Prioritize lookups/review/approval over reproducing desktop administration screens.

## 23. Explicit non-goals for first Android checkpoint

Do not build yet:

- iOS;
- full accounting UI;
- complete Procurement UI before backend release;
- advanced drawing/CAD editor;
- generic report-template designer on phone;
- full company administration on phone;
- AI assistant;
- WhatsApp integration;
- background GPS tracking;
- custom password/auth system for production;
- every planned Feature Registry module merely to make the menu look complete.

## 24. First Android checkpoint definition of done

The first Android checkpoint is ready when a real Android phone can:

1. install the debug APK;
2. log in through the approved development auth flow;
3. establish a native server session securely;
4. load permission/feature context;
5. register the device;
6. list/select authorized projects;
7. open a fast Project Home screen;
8. complete Attendance with local-first behavior;
9. create/update a DPR with core sections and photos;
10. survive offline/reconnect without losing or duplicating data;
11. submit governed records;
12. show only permitted actions;
13. display DPR generation state and open the issued report when ready;
14. logout/revoke local session cleanly;
15. pass Android lint/unit/build CI plus the existing API/web/live-stack gates.

## 25. Instructions to the next ChatGPT session

The user has little/no prior Android development experience. Explain environment setup and Android concepts in granular practical language while still implementing the work.

Do not ask the user to design the architecture again. The decisions in this document are authoritative unless a concrete technical issue requires adjustment.

Before modifying code:

1. inspect `build/platform-foundation`;
2. read this file;
3. read `docs/product/FRONTEND-INTEGRATION-MODULES-1-6.md`;
4. inspect session/authentication/offline/feature-access code;
5. verify current branch head and CI state.

Then start with **Phase A — Mobile backend fit**, followed immediately by **Phase B/C Android skeleton + login/bootstrap**.

Work directly on `build/platform-foundation`. Do not create a new branch.

Make small coherent commits and keep existing API/web behavior working.

Do not call a checkpoint complete until CI relevant to that checkpoint is green.

When an Android decision affects security, offline correctness, tenant isolation or historical business records, prefer server authority and explicit failure over convenient client-side assumptions.
