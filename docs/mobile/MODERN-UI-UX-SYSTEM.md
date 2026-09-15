# Construction OS Mobile — Modern UI/UX System

## Purpose

Construction OS mobile must feel current, fast and intentionally designed. It must not fall back to generic enterprise forms, dense spreadsheet layouts or default Material components arranged without a product-level interaction system.

The visual quality bar is modern high-engagement mobile software: fast navigation, strong hierarchy, card-led surfaces, fluid transitions, gesture support and immediate feedback. Construction OS should borrow interaction principles from polished consumer and game interfaces without looking like a game.

The field context remains the authority. Readability, one-handed use, outdoor contrast, offline clarity and large touch targets are more important than decorative effects.

## Product feel

Construction OS should feel:

- immediate;
- confident;
- compact but not cramped;
- visually layered;
- touch-first;
- gesture-aware;
- calm under error/offline conditions;
- consistent across Modules 1–6.

It should not feel:

- like a web admin panel placed inside an APK;
- like a spreadsheet;
- like a stock Material sample;
- like every section is a separate full-page form;
- animation-heavy for its own sake;
- visually noisy or game-themed.

## Navigation model

Primary project workspaces use a small number of spaces that can be switched both by bottom navigation and horizontal swipe where the gesture is safe.

Initial project spaces:

- Home
- Field
- Crew when permitted
- More

Home / Field / More are horizontally swipeable. Crew is an explicit workflow destination because it can contain deeper navigation and large lists.

Project switching remains directly available from the project header.

Avoid deep hamburger-menu structures for high-frequency field work.

## Cards

Cards are the main action and summary primitive.

Use cards for:

- quick actions;
- active workflow state;
- sync/error state;
- project selection;
- metrics;
- report sections;
- approval summaries;
- photo/upload items.

Cards should use:

- 16–28 dp corner radii depending on hierarchy;
- minimal elevation;
- surface/background contrast before shadows;
- concise text;
- icon + title + short supporting line;
- status chips where useful;
- press feedback through a small scale change.

Do not put an extra `Open` button inside every tappable card. The card itself should be the control unless a secondary action genuinely exists.

## Motion

Motion communicates spatial relationship and state change.

Preferred durations:

- press feedback: 80–140 ms perceived response;
- small state/color transitions: 120–220 ms;
- card expansion/collapse: 180–280 ms;
- page/space transitions: 220–340 ms;
- bottom sheet entrance: platform-standard spring/slide behavior.

Use spring motion for tactile card presses and lightweight transitions.

Avoid:

- long blocking animations;
- animation before local state updates;
- bouncing decorative elements;
- full-screen transitions after every small action;
- motion that delays attendance marking or DPR entry.

Offline/local-first writes must update the UI before any sync animation.

## Gestures

Use gestures where they are discoverable and reversible.

Approved patterns:

- horizontal swipe between peer spaces/tabs;
- swipe-to-reveal secondary row actions when the row also has an obvious tap path;
- pull-to-refresh for online refreshable read surfaces;
- drag only where ordering is a real business capability;
- pinch/zoom only for drawings/media where expected.

Do not make critical operations gesture-only.

Submit, approve, reject, void, delete and other governed/destructive actions must always have an explicit visible path.

## Bottom sheets

Prefer bottom sheets for contextual tasks that should not destroy navigation context, including:

- filters;
- WBS/BOQ selection;
- worker quick actions;
- photo source selection;
- reason/note entry;
- small confirmation flows;
- project switching when the project list is short enough.

Use a full screen when the task requires substantial review, long lists, or governed approval context.

## Status and sync feedback

Field workflows expose these states consistently:

- Saved on device
- Waiting for network
- Syncing
- Synced
- Needs attention

Use compact status pills/chips rather than large banners for healthy states.

Use stronger cards/banners only for:

- conflicts;
- permission changes;
- failed governed operations;
- missing required information;
- session/deployment problems.

Do not use red for ordinary pending/offline states.

## Attendance interaction rules

Attendance is speed-critical and must not become visually overdesigned.

Required interaction priorities:

1. worker identity;
2. current mark;
3. one-tap status update;
4. bulk mark remaining present;
5. filters/search;
6. hours/details;
7. submit/review state.

Use compact cards/chips and high-contrast selected states.

Do not require swiping each worker just to mark Present/Absent. Swipe may expose secondary actions, but primary marking stays one tap.

With 35+ workers, every repeated interaction must remain fast enough to perform continuously without waiting for network or animation completion.

## DPR interaction rules

DPR is section-based. Peer sections may use horizontal swipe navigation:

- Entry
- Crew
- Configured fields
- Photos
- Review

Sections should feel like spaces inside one report, not unrelated pages.

Use compact chips/tabs at the top and preserve report/project/date context.

Work progress, delays and photos use card-style content rather than table-like rows.

Governed lifecycle actions remain explicit.

## Photos

Photos should be visual-first.

Use:

- thumbnail grids or strong media rows;
- visible upload progress;
- tap for detail/full-screen preview;
- contextual Take Photo / Choose Photo controls;
- retry/cancel only when meaningful;
- lightweight status overlay/chip.

Never decode originals into scrolling lists.

## Lookups: WBS, BOQ, Party, Workforce

Large lookup lists should use:

- sticky or persistent search;
- filter chips;
- recent/relevant items before exhaustive browsing where possible;
- cards/rows with strong primary identifier and quiet secondary metadata;
- bottom sheets when invoked as a selector inside another workflow;
- full screens when used as a standalone directory.

Avoid large outlined buttons repeated for every row.

## Typography

Use a clear hierarchy rather than many font sizes.

Recommended roles:

- screen/project title: bold 21–30 sp;
- section title: semibold 17–21 sp;
- row/card title: semibold 15–17 sp;
- body: 14–16 sp;
- metadata: 12–13 sp.

Do not shrink text to fit more controls. Reduce chrome instead.

## Color

Construction OS uses a restrained industrial palette:

- graphite/charcoal foundations;
- warm construction amber as primary accent;
- blue for information/navigation support;
- green for healthy/success state;
- red only for real error/destructive state.

Light and dark themes must both preserve identity.

Avoid extremely bright full-screen surfaces, excessive gradients, or low-contrast gray text.

## Touch targets

Interactive targets should be at least 48 dp in ordinary field use.

Frequently repeated controls may be visually compact while keeping a larger invisible touch area.

Spacing should support gloves, moving users and outdoor use.

## Loading

Prefer:

- cached content immediately;
- skeleton/placeholder only where content is genuinely not available;
- small inline progress for server-authoritative actions;
- optimistic local state for offline-capable actions.

Avoid blocking full-screen spinners after app bootstrap unless the app cannot safely continue.

## Error UX

Errors should explain the action the user can take.

Examples:

- `Saved on device. Waiting for network.`
- `This report changed on the server. Review both versions.`
- `You no longer have permission to approve this report.`
- `2 workers are still unmarked.`

Never expose raw stack traces or transport jargon to field users.

## Performance

Modern UI does not justify expensive UI.

Rules:

- keep transitions GPU-friendly;
- animate transform/alpha before expensive layout where practical;
- no blur-heavy backgrounds on core field screens;
- no full-resolution image work in composition;
- stable list keys;
- lazy lists/grids for large datasets;
- avoid recomposing entire screens after a single attendance mark;
- use Room/Flow as the source for field screens.

## Accessibility and reduced motion

Do not communicate status by color alone.

Icons and motion must have semantic alternatives.

The design should remain understandable with animations disabled/reduced.

## Implementation rule

Any new mobile screen should reuse the Construction OS design primitives before introducing one-off styling.

New UI should be reviewed against these questions:

1. Can the most common action be completed in one or two obvious taps?
2. Does the screen feel like a native 2026 mobile product rather than a web form?
3. Is network state visible without dominating the page?
4. Are permissions and governed states still server-authoritative?
5. Does the UI remain usable outdoors and one-handed?
6. Is motion helping orientation/feedback rather than decorating the screen?
7. Is the same interaction pattern already available elsewhere in Construction OS?

If a custom interaction fails these checks, prefer the simpler existing pattern.
