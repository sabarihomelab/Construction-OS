# Product Definition of Done

A Construction OS feature is complete only when all applicable items below are satisfied.

## Functional

- A real user can complete the intended construction workflow end to end.
- Data is persisted in the canonical domain model.
- Required validations and business rules are enforced server-side.
- Empty, loading, success, validation, conflict and failure states are implemented.
- Changes are reversible or explicitly irreversible where the business process requires it.

## Security and privacy

- Authentication is required unless the route is intentionally public.
- Authorization is enforced server-side for organization, project, resource and action scope.
- Tenant isolation is covered by automated tests.
- Sensitive values are not written to application logs.
- Financial/privileged actions create audit events.
- File access uses authorization checks and short-lived access where applicable.
- Inputs are validated and output encoding is appropriate for the destination.

## Reliability

- Database writes use transactional boundaries appropriate to the workflow.
- Retried requests do not create duplicate financial/critical records when idempotency is required.
- Long-running side effects use durable jobs/outbox events.
- Expected failure modes are observable without exposing secrets to the user.

## Quality

- Unit tests cover non-trivial domain rules.
- API/integration tests cover the primary workflow.
- CI lint/type/build checks pass.
- Database migrations are included for schema changes.
- API contracts and key domain terminology are documented.

## User experience

- The workflow is usable on the target device class.
- Common field actions minimize typing and unnecessary navigation.
- Keyboard/accessibility semantics are considered for office workflows.
- Destructive actions are clear and protected from accidental activation.
- No placeholder buttons, fake counters or sample results are shipped as production functionality.

## Operations

- Required environment/configuration values are documented.
- Health/readiness behavior is defined for external dependencies.
- Metrics/audit signals exist for important failures and privileged actions.
- Backup/restore impact is understood for newly introduced persistent data.

## Documentation and support

- End-user behavior is documented when the feature is non-obvious.
- Admin configuration is documented.
- Support troubleshooting guidance exists for expected operational failures.

A screen, route, model or button by itself does not satisfy this definition.
