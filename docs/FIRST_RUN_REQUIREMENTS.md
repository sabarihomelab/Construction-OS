# First Run Requirements

This document lists the real configuration needed to make Construction OS run. Values marked **required now** are necessary for the local development baseline. Other values become required only when their feature is enabled.

## Required now

### Database

- `DATABASE_URL`
  - PostgreSQL connection string used by the API.
  - Local default may point to the Docker PostgreSQL service.

### Application

- `APP_NAME`
  - Human-readable application name.
- `ENVIRONMENT`
  - One of `development`, `test`, `staging`, `production`.
- `WEB_ORIGIN`
  - Allowed browser origin for CORS.
- `DEPLOYMENT_ID`
  - Stable, non-secret identifier for this Construction OS deployment.
  - Local development uses `local-development`.
  - A customer production deployment must use its own stable value and must not be reused for another customer deployment.

### Security

- `APP_SECRET_KEY`
  - Cryptographically random application secret.
  - Never commit a production value to source control.

## Initial company bootstrap

After migrations are applied to a new empty installation, create the first company and protected administrator membership with the operator-only bootstrap command:

```powershell
.\bootstrap-company.ps1 `
  -CompanyName "Example Construction Pvt Ltd" `
  -CompanySlug "example-construction" `
  -AdminEmail "admin@example.com" `
  -AdminDisplayName "Company Administrator"
```

`-LegalName` is optional when the legal name differs from the operating name.

The bootstrap command:

- refuses to run when an organization already exists
- creates the organization and India localization settings (`IN`, `en-IN`, `Asia/Kolkata`, `INR`, metric)
- creates the initial active administrator user and organization membership
- creates a protected company-administrator role and grants the migrated active permission catalog
- initializes organization authorization state
- records the bootstrap as a critical audit event
- prints the created `organization_id`; keep this value for deployment binding

The bootstrap command does **not** create a public first-run API and does not invent or store an identity-provider password. The administrator identity must later be bound to the configured authentication provider before production login is possible.

## Bind a production deployment to its company

Construction OS production uses a dedicated-company deployment boundary. After the company bootstrap succeeds:

1. Set `DEPLOYMENT_ID` to a stable identifier for that customer deployment, for example `acme-prod-01`.
2. Set `DEPLOYMENT_ORGANIZATION_ID` to the `organization_id` printed by `bootstrap-company.ps1`.
3. Start the production API only after both values are configured.

`DEPLOYMENT_ORGANIZATION_ID` is intentionally allowed to be empty while the operator-only bootstrap command creates the first company. The production API itself refuses to start until the binding is present.

The binding is enforced in addition to normal organization, membership, role, project and permission checks. Session creation and session validation reject memberships outside the configured company.

The unauthenticated mobile bootstrap endpoint is:

```text
GET /api/v1/deployment/bootstrap
```

It exposes only safe connection/display metadata such as deployment ID, company ID/name/slug, environment label and API path. It must never expose database URLs, passwords, signing secrets, storage credentials, KMS keys or other private deployment configuration.

## Android company connection

The Android APK is shared across customers, but each installation connects to a selected customer deployment before sign-in.

- The first-run screen asks for the company Construction OS server address.
- Production requires HTTPS.
- The app validates the server through `/api/v1/deployment/bootstrap` before creating the normal API client.
- Authentication then occurs only against that selected deployment.
- The selected deployment ID namespaces the encrypted bearer session, Room database, project selection and WorkManager sync jobs.
- Switching company does not make another company's cached/offline data visible or send its queued mutations to the newly selected server.
- Database credentials are never stored in or sent to the Android client.

A short company code, QR code or invitation-link resolver may be added later as a separate onboarding/control-plane service. It should resolve to the same verified deployment bootstrap contract rather than bypass it.

## Required before authentication is production-ready

- Authentication issuer/provider configuration or internal identity service configuration.
- Session/token signing and validation configuration.
- MFA policy.
- Password/reset/email-verification delivery configuration if local credentials are supported.
- Binding of the bootstrapped administrator identity to the approved authentication provider.

## Required before file/document features are enabled

- Object storage endpoint/provider.
- Storage bucket/container names.
- Encryption/KMS configuration if supplied by the deployment environment.
- Maximum upload limits and accepted file-type policy.
- Malware scanning service/process for uploaded files.

## Required before notifications are enabled

- Transactional email provider or SMTP relay.
- Sender identity/domain.
- Optional SMS/push provider configuration.

## Required before AI features are enabled

AI is disabled by default until explicitly configured.

- AI provider selection.
- Provider API credentials or private-model endpoint.
- Tenant AI policy defaults.
- Allowed AI feature list.
- Data-retention policy for AI requests/responses.

No AI credential is required for core Construction OS operation.

## Required before production launch

- Production domain and TLS certificates/termination.
- Production PostgreSQL instance and backup/restore policy.
- Object storage and backup/lifecycle policy.
- Secret manager.
- Centralized structured logs with sensitive-data filtering.
- Metrics and alerting destination.
- Error tracking configured to avoid collecting sensitive payloads.
- Email delivery.
- Disaster recovery targets (RPO/RTO).
- Data retention/deletion policy.
- Tenant onboarding/offboarding process.
- Support contact and escalation routing.
- Privacy policy, terms and customer data-processing terms appropriate to the target market.

## Development principle

Do not invent values for services that do not exist yet. New features must update this file with the exact runtime configuration they require. `.env.example` may contain safe local defaults and variable names only; secrets never belong in Git.
