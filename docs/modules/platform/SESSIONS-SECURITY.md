# Sessions and Request Security

## Purpose

Construction OS uses server-controlled opaque sessions. Authentication providers establish identity; Construction OS then creates its own application session tied to an active organization membership.

This design keeps tenant authorization current and allows immediate server-side revocation without encoding long-lived permission state into a browser token.

## Session token

The browser receives a high-entropy opaque session token in a cookie.

The raw token is never persisted in PostgreSQL. Only a SHA-256 hash is stored in `sessions.token_hash`. SHA-256 is appropriate here because the token is generated with high cryptographic entropy; this is not password hashing.

The session cookie is:

- HttpOnly
- Secure in production
- SameSite Lax or Strict according to supported deployment configuration
- scoped to the application path

Production configuration refuses to start with insecure session cookies.

## CSRF protection

A separate high-entropy CSRF value is issued alongside the session. The raw CSRF value is available to the browser and must be sent in the `X-CSRF-Token` header for protected state-changing requests.

Only its SHA-256 hash is stored with the server session, binding the CSRF token to that session.

SameSite cookies are defense in depth and do not replace explicit CSRF validation for protected writes.

## Timeout policy

Current foundation policy:

- idle timeout: 180 seconds
- absolute timeout: 28,800 seconds (8 hours)
- database touch interval: 30 seconds

The short touch interval avoids a session-table write on every API request while still enforcing the requested three-minute idle policy.

Idle expiry may never be extended past the absolute expiry.

## Session validation

Every protected request validates:

1. session token exists and matches a stored hash;
2. session has not been revoked;
3. absolute timeout has not passed;
4. idle timeout has not passed;
5. membership still exists and is active;
6. membership still belongs to the session user;
7. user still exists and is active.

An inactive user or membership causes the session to be revoked.

## Authorization freshness

The session does not contain a frozen permission list.

`GET /api/v1/session/context` resolves current permissions and features from the active membership every time the context is requested. Backend business APIs will independently evaluate authorization for protected actions.

Role, permission, and feature changes therefore do not require logout/login to become effective.

## Authentication methods

The session schema can record how identity was established:

- OIDC
- local password
- passkey
- recovery flow

It also records authentication strength:

- single factor
- MFA
- phishing resistant

Authentication provider implementation is intentionally separate from the session layer. This allows self-hosted/local and enterprise identity-provider options without changing business authorization.

## MFA and step-up

The schema records authentication level and the time MFA was verified. High-risk actions will later be able to require recent step-up authentication rather than trusting a session that satisfied only basic authentication hours earlier.

MFA enrollment, passkeys, TOTP, and recovery-code implementation belongs to the Authentication module and must use mature cryptographic libraries/protocols rather than custom algorithms.

## Revocation

Sessions can be revoked individually or for all sessions belonging to a user.

Expected revocation triggers include:

- logout
- idle timeout
- absolute timeout
- account disable/suspension
- membership suspension/end
- password/security reset
- MFA reset where policy requires it
- suspicious security event
- administrative forced logout

Permission changes normally do not revoke the session because authorization is evaluated from current server state.

## Data minimization

The session table intentionally does not currently persist raw cookies, passwords, API secrets, or unrestricted client fingerprint data.

IP/device/security-event retention will be defined with the Audit and Security Monitoring modules so collection is purposeful, access-controlled, and retention-aware.

## Current API surface

Public:

- health endpoint

Session protected:

- `GET /api/v1/session/context`
- `POST /api/v1/session/logout` (CSRF protected)

There is intentionally no temporary/fake login endpoint. Authentication/session issuance will be added through the Authentication module.

## Change impact

Changing timeout, cookie, CSRF, authentication-strength, or revocation behavior requires security impact assessment.

Historical business data is not rewritten by a session-policy change. Existing sessions may be revoked when required by a security policy migration, but business records remain unchanged.
