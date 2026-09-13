# Construction OS Android Self-Test Guide

This guide is for local development and personal testing of the Android Modules 1-6 checkpoint.

## 1. Use the development branch

```powershell
git checkout build/platform-foundation
git pull
```

## 2. Install Construction OS locally

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Use a `development` environment and a local database for the simplest self-test setup.

## 3. Enable the development mobile login

Open `.env` and set:

```text
NATIVE_DEV_AUTH_ENABLED=true
NATIVE_DEV_AUTH_SECRET=construction-os-local-test-2026
```

The development secret must be at least 16 characters. Never enable this provider in production.

## 4. Create the first company and administrator

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap-company.ps1 `
  -CompanyName "Sabari Test Construction" `
  -CompanySlug "sabari-test" `
  -AdminEmail "sabari@test.local" `
  -AdminDisplayName "Sabari"
```

Use the same administrator email when seeding the demo project.

## 5. Seed realistic Modules 1-6 demo data

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap-demo-data.ps1 `
  -AdminEmail "sabari@test.local"
```

The command is development/test only and is safe to rerun. If `DEMO-001` already exists, the existing demo project is left unchanged.

The seed creates:

- one active project: `DEMO-001 - Riverside Residency - Phase 1`;
- five project Parties;
- a 19-code WBS hierarchy;
- one approved BOQ with 32 realistic items;
- one submitted Estimate for mobile approval testing;
- one draft Budget for mobile approval testing;
- four crews and 40 active workers;
- three approved historical attendance days;
- two historical DPRs, including one rejected report and one editable draft;
- WBS/BOQ-linked DPR work progress and a sample delay/blocker;
- three configured DPR custom fields.

Today's Attendance and today's DPR are deliberately not pre-created so the tester can exercise the real create/offline/sync/submit flows.

## 6. Start the local backend and web application

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

Expected local addresses:

```text
Web:       http://localhost:3000
API:       http://localhost:8000
Readiness: http://localhost:8000/health/ready
API Docs:  http://localhost:8000/docs
```

Confirm the readiness endpoint returns `ready` before starting Android.

## 7. Test with an Android emulator

Open `apps/mobile` in Android Studio and run the `app` debug configuration.

At **Connect Company**, use:

```text
http://10.0.2.2:8000
```

Then sign in with the administrator email used during company bootstrap and the value of `NATIVE_DEV_AUTH_SECRET`.

## 8. Test with a physical Android phone

Enable USB debugging, connect the phone, then run:

```powershell
adb devices
adb reverse tcp:8000 tcp:8000
```

Install/run the debug app from Android Studio and use this company server address:

```text
http://127.0.0.1:8000
```

Keep the USB connection active while using `adb reverse`.

## 9. Recommended manual test order

1. Connect Company and sign in.
2. Select `DEMO-001`.
3. Review Home / Field / More navigation and project switching.
4. Search Party Directory.
5. Search and browse WBS / Cost Codes.
6. Search approved BOQ items and confirm financial fields remain permission-safe.
7. Open Estimating / Budget and approve the submitted Estimate and draft Budget.
8. Open Workforce, switch Workers / Crews, search and filter the 40 workers.
9. Create today's Attendance register and mark at least 35 workers.
10. Turn networking off, keep editing Attendance, close/reopen the app, then reconnect and confirm one clean sync without duplicate updates.
11. Submit/approve Attendance as permitted.
12. Create today's DPR and verify the approved Attendance Crew summary.
13. Add WBS/BOQ-linked work progress, notes and a delay/blocker.
14. Complete the configured custom fields.
15. Capture a camera photo and choose a gallery photo.
16. Interrupt an upload, reconnect and confirm upload resumes without duplicate attachments.
17. Submit the DPR and test Review / Approve / Reject / Reopen / Void according to permissions and state.
18. If approved, observe asynchronous report generation and open the issued file when ready.

## 10. What to record when something feels wrong

Capture:

- screenshot or screen recording;
- exact screen and project;
- what you tapped;
- what you expected;
- what happened;
- whether the phone was online/offline;
- whether you had just killed/reopened the app.

For UI feedback also note excessive scrolling, awkward one-handed use, unclear icons, slow taps, swipe conflicts, unreadable outdoor contrast, keyboard issues and confusing sync states.
