from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.configuration.models import ConfigurationValue
from app.modules.configuration.registry import CONFIGURATION_BY_KEY, ConfigurationMutability
from app.modules.setup.models import ConfigurationHealthStatus
from app.modules.setup.service import upsert_configuration_health


@dataclass(frozen=True, slots=True)
class ConfigurationHealthIssue:
    code: str
    configuration_key: str
    summary: str


async def inspect_registered_configuration(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> list[ConfigurationHealthIssue]:
    rows = await db.scalars(
        select(ConfigurationValue).where(ConfigurationValue.organization_id == organization_id)
    )
    issues: list[ConfigurationHealthIssue] = []
    for row in rows.all():
        definition = CONFIGURATION_BY_KEY.get(row.configuration_key)
        if definition is None:
            issues.append(
                ConfigurationHealthIssue(
                    code="unregistered_key",
                    configuration_key=row.configuration_key,
                    summary="Persisted configuration key is not registered by this application version.",
                )
            )
            continue
        if definition.module_key != row.module_key:
            issues.append(
                ConfigurationHealthIssue(
                    code="module_mismatch",
                    configuration_key=row.configuration_key,
                    summary="Persisted configuration module does not match the protected definition.",
                )
            )
        if definition.mutability == ConfigurationMutability.PROTECTED:
            issues.append(
                ConfigurationHealthIssue(
                    code="protected_override",
                    configuration_key=row.configuration_key,
                    summary="Protected platform configuration must not have a tenant override.",
                )
            )
        elif row.scope_type not in definition.allowed_scopes:
            issues.append(
                ConfigurationHealthIssue(
                    code="scope_not_allowed",
                    configuration_key=row.configuration_key,
                    summary="Persisted configuration uses a scope not allowed by its definition.",
                )
            )
    return issues


async def publish_configuration_health(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> list[ConfigurationHealthIssue]:
    issues = await inspect_registered_configuration(db, organization_id=organization_id)
    status = ConfigurationHealthStatus.HEALTHY if not issues else ConfigurationHealthStatus.ATTENTION
    summary = (
        "Registered configuration is consistent."
        if not issues
        else f"{len(issues)} configuration issue(s) require attention."
    )
    await upsert_configuration_health(
        db,
        organization_id=organization_id,
        check_key="configuration.registry_consistency",
        target_type="organization",
        target_id=str(organization_id),
        status=status,
        summary=summary,
        details={
            "issues": [
                {
                    "code": issue.code,
                    "configuration_key": issue.configuration_key,
                    "summary": issue.summary,
                }
                for issue in issues[:100]
            ],
            "truncated": len(issues) > 100,
        },
    )
    return issues
