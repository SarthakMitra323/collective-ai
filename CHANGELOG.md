# Changelog

All notable changes to this project are documented in this file.

## [2026-04-14] - Stability, Auth, and Local Dev Fixes

### Added
- Added a live backend status badge in the dashboard header.
- Added client request tracing for chat requests (`X-Client-Request-Id`) and backend echo (`request_id`) for easier debugging.
- Added clearer frontend error reporting fields (`backendLabel`, `traceId`, stack logging).
- Added session timestamp stamping helper for login flow (`cai_login_ts`).

### Changed
- Improved local backend target logic for chat requests:
  - Localhost now targets FastAPI default backend port first (`http://localhost:3000`).
- Improved chat request timeout handling:
  - Longer timeout for localhost.
  - Better timeout messages shown to users.
- Updated backend startup from deprecated `on_event("startup")` to FastAPI lifespan handlers.
- Expanded default CORS configuration to include localhost and 127.0.0.1 development origins.

### Fixed
- Fixed login redirect loop back to `app.html` caused by missing session timestamp stamping.
- Fixed `withTimeout is not defined` runtime error in dashboard chat flow.
- Fixed `isValidChatPayload is not defined` scope error.
- Fixed false-positive backend checks by validating expected API payload shape (not only HTTP 200).
- Fixed intermittent frontend/backend route selection confusion by improving fallback behavior and diagnostics.
- Fixed local preflight failures (`OPTIONS /api/chat 400`) by correcting local CORS defaults.

## [2026-04-12] - Render and Vercel Reliability Hardening

### Added
- Added defensive timeout wrappers for RAG and chat generation in backend.
- Added retries with backoff for transient upstream errors in dashboard fetch flow.

### Changed
- Updated Render service startup and environment defaults for improved reliability.
- Updated Vercel rewrite/header configuration for API proxying behavior.
- Improved backend health/readiness handling.

### Fixed
- Reduced worker timeout and memory pressure issues by limiting heavy startup work.
- Improved behavior under upstream 5xx responses and network hiccups.

## [2026-04-11] - Initial Production Stabilization

### Changed
- Migrated backend model configuration and production settings to stable environment-driven defaults.
- Updated frontend/backend integration paths and diagnostics.

### Fixed
- Addressed major backend unavailability scenarios and proxy path failures.
