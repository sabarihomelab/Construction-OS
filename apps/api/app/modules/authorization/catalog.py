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
    PermissionSpec(key="admin.configuration.view", module="admin", resource="configuration", action="view", description="View registered company, project-template and project configuration definitions and effective values.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="admin.configuration.manage", module="admin", resource="configuration", action="manage", description="Create versioned company, project-template and project configuration overrides.", risk=PermissionRisk.CRITICAL),
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
    PermissionSpec(key="projects.project.create", module="projects", resource="project", action="create", description="Create projects for the company.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="projects.project.update", module="projects", resource="project", action="update", description="Update project details within the authorized scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="projects.project.archive", module="projects", resource="project", action="archive", description="Move projects into closeout, complete, or archived states within the authorized scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="projects.membership.view", module="projects", resource="membership", action="view", description="View project team memberships within the authorized scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="projects.membership.manage", module="projects", resource="membership", action="manage", description="Add, suspend, end, and assign roles to project memberships.", risk=PermissionRisk.CRITICAL),
    PermissionSpec(key="documents.document.view", module="documents", resource="document", action="view", description="View project documents and issued revisions within the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="documents.document.create", module="documents", resource="document", action="create", description="Create managed documents and draft revisions within the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="documents.document.publish", module="documents", resource="document", action="publish", description="Publish and supersede controlled document revisions within the authorized project scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="documents.document.manage", module="documents", resource="document", action="manage", description="Manage document folders, metadata, specifications, archival and document control.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="drawings.drawing.view", module="drawings", resource="drawing", action="view", description="View drawing sets, sheets and published revisions within the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="drawings.drawing.revise", module="drawings", resource="drawing", action="revise", description="Create sheets and drawing revisions within the authorized project scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="drawings.drawing.publish", module="drawings", resource="drawing", action="publish", description="Publish or supersede controlled drawing revisions.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="drawings.markup.manage", module="drawings", resource="markup", action="manage", description="Create, update and retire drawing markups.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="drawings.measurement.manage", module="drawings", resource="measurement", action="manage", description="Create calibrations and authoritative drawing measurements.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="drawings.comparison.run", module="drawings", resource="comparison", action="run", description="Run drawing revision comparisons and overlays.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="drawings.drawing.manage", module="drawings", resource="drawing", action="manage", description="Manage drawing sets, processing, archival and drawing configuration.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="rfis.rfi.view", module="rfis", resource="rfi", action="view", description="View RFIs, responses, references and history in the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="rfis.rfi.create", module="rfis", resource="rfi", action="create", description="Create draft RFIs in the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="rfis.rfi.update", module="rfis", resource="rfi", action="update", description="Edit and open RFIs and add controlled references in the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="rfis.rfi.respond", module="rfis", resource="rfi", action="respond", description="Add proposed or official RFI responses in the authorized project scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="rfis.rfi.close", module="rfis", resource="rfi", action="close", description="Close answered RFIs in the authorized project scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="rfis.rfi.manage", module="rfis", resource="rfi", action="manage", description="Manage RFI responsibility and controlled void actions.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="submittals.submittal.view", module="submittals", resource="submittal", action="view", description="View Submittals, revisions, reviews, references and history in the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="submittals.submittal.create", module="submittals", resource="submittal", action="create", description="Create draft Submittals in the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="submittals.submittal.update", module="submittals", resource="submittal", action="update", description="Edit Submittals, create revisions and manage controlled references.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="submittals.submittal.submit", module="submittals", resource="submittal", action="submit", description="Submit a Submittal revision for review and assign the reviewer.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="submittals.submittal.review", module="submittals", resource="submittal", action="review", description="Add review comments and issue official Submittal decisions.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="submittals.submittal.close", module="submittals", resource="submittal", action="close", description="Close approved Submittals in the authorized project scope.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="submittals.submittal.manage", module="submittals", resource="submittal", action="manage", description="Manage Submittal responsibility and controlled void actions.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="field.daily_report.view", module="field", resource="daily_report", action="view", description="View Daily Reports within the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="field.daily_report.create", module="field", resource="daily_report", action="create", description="Create Daily Report drafts within the authorized project scope.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="field.daily_report.update", module="field", resource="daily_report", action="update", description="Update Daily Report drafts and configured sections.", risk=PermissionRisk.MEDIUM),
    PermissionSpec(key="field.daily_report.submit", module="field", resource="daily_report", action="submit", description="Submit Daily Reports using effective project configuration.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="field.daily_report.approve", module="field", resource="daily_report", action="approve", description="Approve or reject Daily Reports requiring review.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="field.daily_report.manage", module="field", resource="daily_report", action="manage", description="Perform controlled Daily Report administrative actions.", risk=PermissionRisk.HIGH),
    PermissionSpec(key="finance.budget.view", module="finance", resource="budget", action="view", description="View project budget information within the authorized scope.", risk=PermissionRisk.HIGH),
)

PERMISSIONS_BY_KEY = {permission.key: permission for permission in PERMISSION_CATALOG}

if len(PERMISSIONS_BY_KEY) != len(PERMISSION_CATALOG):
    raise RuntimeError("Permission catalog keys must be unique")
