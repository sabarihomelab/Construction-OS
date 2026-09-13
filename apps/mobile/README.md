# Construction OS Android

Native Android client for Construction OS. The app follows `docs/mobile/ANDROID-APP-WORK-INSTRUCTION.md` and keeps the backend authoritative for identity, permissions, feature visibility, approvals, financial values, and revision history.

## Baseline

- Package: `com.constructionos.app`
- Minimum Android: API 26
- Compile / target SDK: API 37
- UI: Jetpack Compose + Material 3
- Navigation: Navigation Compose
- Async state: Kotlin Coroutines / Flow
- Local data: Room
- Background sync: WorkManager
- API: Retrofit + OkHttp

Debug builds point at `http://10.0.2.2:8000/api/v1/` for the Android emulator. Release builds disable cleartext traffic and require a real HTTPS API URL before distribution.

The initial scaffold intentionally contains no Attendance or DPR business rules. Those workflows are added only after session bootstrap, secure token storage, access-context loading, device registration, and offline infrastructure are implemented.
