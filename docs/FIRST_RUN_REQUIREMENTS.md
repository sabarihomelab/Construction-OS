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

## Required before authentication is production-ready

- Authentication issuer/provider configuration or internal identity service configuration.
- Session/token signing and validation configuration.
- MFA policy.
- Password/reset/email-verification delivery configuration if local credentials are supported.
- Initial platform administrator bootstrap procedure.

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
