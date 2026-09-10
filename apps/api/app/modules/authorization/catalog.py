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
    PermissionSpec(key="admin.settings.view", module="admin", resource="settings", action="view", description="View company administration settings.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="admin.operations.view", module="admin", resource="operations", action="view", description="View company operational health and capacity information.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.operations.storage.view", module="admin", resource="operations_storage", action="view", description="View storage usage and storage-health information.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.operations.security.view", module="admin", resource="operations_security", action="view", description="View security-posture information exposed to company administrators.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="admin.operations.integrations.view", module="admin", resource="operations_integrations", action="view", description="View integration and synchronization health.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.operations.audit.view", module="admin", resource="operations_audit", action="view", description="View permitted operational audit diagnostics.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="admin.operations.manage", module="admin", resource="operations", action="manage", description="Perform permitted operational remediation actions.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="admin.operations.jobs.view", module="admin", resource="operations_jobs", action="view", description="View tenant-scoped background job status and failure diagnostics.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.operations.jobs.manage", module="admin", resource="operations_jobs", action="manage", description="Retry, cancel, or otherwise manage tenant-scoped background jobs.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="admin.workflow.view", module="admin", resource="workflow", action="view", description="View company workflow definitions, versions, states, and transitions.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="admin.workflow.manage", module="admin", resource="workflow", action="manage", description="Create, version, publish, retire, and configure company workflows.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.setup.view", module="admin", resource="setup", action="view", description="View guided setup, configuration templates, and configuration health.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="admin.setup.manage", module="admin", resource="setup", action="manage", description="Create, publish, validate, and apply company configuration templates.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.custom_field.view", module="admin", resource="custom_field", action="view", description="View custom field definitions and configuration.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="admin.custom_field.manage", module="admin", resource="custom_field", action="manage", description="Create, change, retire, and configure custom field definitions.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="integrations.connector.view", module="integrations", resource="connector", action="view", description="View configured external-system connectors and sync status.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="integrations.connector.manage", module="integrations", resource="connector", action="manage", description="Configure, enable, disable, and reauthorize external-system connectors.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="integrations.sync.run", module="integrations", resource="sync", action="run", description="Start an authorized connector synchronization or ingestion run.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="reporting.report.view", module="reporting", resource="report", action="view", description="View permitted reports and dashboards.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="reporting.report.create", module="reporting", resource="report", action="create", description="Create personal or permitted shared saved views and reports.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="reporting.report.manage", module="reporting", resource="report", action="manage", description="Publish and manage shared company report definitions and dashboards.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="reporting.report.export", module="reporting", resource="report", action="export", description="Generate permitted PDF, XLSX, or CSV report outputs.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="data.export.create", module="data", resource="export", action="create", description="Request authorized tenant, project, or module data exports.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="data.export.download", module="data", resource="export", action="download", description="Download completed authorized data exports.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="data.export.audit", module="data", resource="export_audit", action="include", description="Include permitted audit history in a data export.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="data.governance.view", module="data", resource="governance", action="view", description="View retention, legal hold and lifecycle policies.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="data.governance.manage", module="data", resource="governance", action="manage", description="Create and publish retention and legal-hold configuration.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="data.lifecycle.execute", module="data", resource="lifecycle", action="execute", description="Execute approved archival or deletion lifecycle actions.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="security.role.view", module="security", resource="role", action="view", description="View roles and their assigned capabilities.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="security.role.manage", module="security", resource="role", action="manage", description="Create, update, clone, assign, and retire company roles.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="help.content.view", module="help", resource="content", action="view", description="View Construction OS help and product guidance."),
    PermissionSpec(key="help.knowledge.manage", module="help", resource="knowledge", action="manage", description="Manage company-specific help and knowledge sources.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="files.file.view", module="files", resource="file", action="view", description="View file metadata and permitted attachments within the authorized scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="files.file.download", module="files", resource="file", action="download", description="Download permitted files and file versions within the authorized scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="files.file.upload", module="files", resource="file", action="upload", description="Upload and attach files within the authorized scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="files.file.manage", module="files", resource="file", action="manage", description="Manage file versions, retention, links, retirement, and controlled deletion.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="projects.project.view", module="projects", resource="project", action="view", description="View projects within the authorized scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="field.daily_log.view", module="field", resource="daily_log", action="view", description="View daily logs within the authorized scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="finance.budget.view", module="finance", resource="budget", action="view", description="View project budget information within the authorized scope.", risk=PermissionRisk.HIGH),
)

PERMISSIONS_BY_KEY = {permission.key: permission for permission in PERMISSION_CATALOG}

if len(PERMISSIONS_BY_KEY) != len(PERMISSION_CATALOG):
    raise RuntimeError("Permission catalog keys must be unique")
