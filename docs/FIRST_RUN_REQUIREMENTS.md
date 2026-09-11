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

The bootstrap command does **not** create a public first-run API and does not invent or store an identity-provider password. The administrator identity must later be bound to the configured authentication provider before production login is possible.

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
