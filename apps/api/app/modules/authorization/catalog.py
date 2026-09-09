from dataclasses import dataclass

from app.modules.authorization.models import PermissionRisk


@dataclass(frozen=True, slots=True)
class PermissionSpec:
    key: str
    module: str
    resource: str
    action: str
    description: str
    risk: PermissionRisk = PermissionRisk.LOW


PERMISSION_CATALOG: tuple[PermissionSpec, ...] = (
    PermissionSpec(
        key="admin.settings.view",
        module="admin",
        resource="settings",
        action="view",
        description="View company administration settings.",
        risk=PermissionRisk.MEDIUM,
    ),
    PermissionSpec(
        key="admin.operations.view",
        module="admin",
        resource="operations",
        action="view",
        description="View company operational health and capacity information.",
        risk=PermissionRisk.HIGH,
    ),
    PermissionSpec(
        key="security.role.view",
        module="security",
        resource="role",
        action="view",
        description="View roles and their assigned capabilities.",
        risk=PermissionRisk.HIGH,
    ),
    PermissionSpec(
        key="security.role.manage",
        module="security",
        resource="role",
        action="manage",
        description="Create, update, clone, assign, and retire company roles.",
        risk=PermissionRisk.CRITICAL,
    ),
    PermissionSpec(
        key="help.content.view",
        module="help",
        resource="content",
        action="view",
        description="View Construction OS help and product guidance.",
    ),
    PermissionSpec(
        key="projects.project.view",
        module="projects",
        resource="project",
        action="view",
        description="View projects within the authorized scope.",
        risk=PermissionRisk.MEDIUM,
    ),
    PermissionSpec(
        key="field.daily_log.view",
        module="field",
        resource="daily_log",
        action="view",
        description="View daily logs within the authorized scope.",
        risk=PermissionRisk.MEDIUM,
    ),
    PermissionSpec(
        key="finance.budget.view",
        module="finance",
        resource="budget",
        action="view",
        description="View project budget information within the authorized scope.",
        risk=PermissionRisk.HIGH,
    ),
)

PERMISSIONS_BY_KEY = {permission.key: permission for permission in PERMISSION_CATALOG}

if len(PERMISSIONS_BY_KEY) != len(PERMISSION_CATALOG):
    raise RuntimeError("Permission catalog keys must be unique")
