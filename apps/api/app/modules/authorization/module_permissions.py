from dataclasses import dataclass

from app.modules.authorization.models import PermissionRisk


@dataclass(frozen=True, slots=True)
class ModulePermissionDefinition:
    key: str
    module: str
    resource: str
    action: str
    description: str
    risk: PermissionRisk = PermissionRisk.LOW


MODULE_PERMISSION_DEFINITIONS: tuple[ModulePermissionDefinition, ...] = (
    ModulePermissionDefinition("safety.module.view", "safety", "module", "view", "Access Safety, Inspections, and Punch within authorized projects.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("safety.record.view", "safety", "record", "view", "View permitted safety records and corrective actions.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.record.create", "safety", "record", "create", "Create project safety records.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.record.update", "safety", "record", "update", "Update open safety records and corrective actions.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.record.close", "safety", "record", "close", "Close resolved safety records.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.record.manage", "safety", "record", "manage", "Perform controlled safety-record administration.", PermissionRisk.CRITICAL),
    ModulePermissionDefinition("safety.inspection.view", "safety", "inspection", "view", "View inspection templates and project inspection runs.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("safety.inspection.create", "safety", "inspection", "create", "Create project inspection runs.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("safety.inspection.execute", "safety", "inspection", "execute", "Record and submit inspection results.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.inspection.review", "safety", "inspection", "review", "Approve or reject inspections through shared Workflow.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.inspection.manage", "safety", "inspection", "manage", "Create, publish, and retire inspection templates.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.punch.view", "safety", "punch", "view", "View Punch items within the authorized project.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("safety.punch.create", "safety", "punch", "create", "Create Punch items within the authorized project.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("safety.punch.update", "safety", "punch", "update", "Update open Punch items.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("safety.punch.close", "safety", "punch", "close", "Close completed Punch items.", PermissionRisk.HIGH),
    ModulePermissionDefinition("safety.punch.manage", "safety", "punch", "manage", "Perform controlled Punch administration.", PermissionRisk.HIGH),
    ModulePermissionDefinition("equipment.module.view", "equipment", "module", "view", "Access Equipment and Materials within permitted company and projects.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("equipment.asset.view", "equipment", "asset", "view", "View company equipment assets.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("equipment.asset.manage", "equipment", "asset", "manage", "Create, update and retire company equipment assets.", PermissionRisk.HIGH),
    ModulePermissionDefinition("equipment.assignment.view", "equipment", "assignment", "view", "View project equipment assignments.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("equipment.assignment.manage", "equipment", "assignment", "manage", "Assign and release equipment within authorized projects.", PermissionRisk.HIGH),
    ModulePermissionDefinition("equipment.maintenance.view", "equipment", "maintenance", "view", "View equipment maintenance records.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("equipment.maintenance.manage", "equipment", "maintenance", "manage", "Create and manage equipment maintenance records.", PermissionRisk.HIGH),
    ModulePermissionDefinition("materials.material.view", "materials", "material", "view", "View the company material catalog.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("materials.material.manage", "materials", "material", "manage", "Create, update and retire material catalog records.", PermissionRisk.HIGH),
    ModulePermissionDefinition("materials.plan.view", "materials", "material_plan", "view", "View planned project material quantities.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("materials.plan.manage", "materials", "material_plan", "manage", "Create and revise project material plans.", PermissionRisk.HIGH),
    ModulePermissionDefinition("materials.delivery.view", "materials", "delivery", "view", "View project material deliveries.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("materials.delivery.manage", "materials", "delivery", "manage", "Create, receive, reject and correct project material deliveries.", PermissionRisk.HIGH),
    ModulePermissionDefinition("meetings.meeting.view", "meetings", "meeting", "view", "View meetings, minutes, attendees, agenda and references in authorized projects.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.meeting.create", "meetings", "meeting", "create", "Create project meetings.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.meeting.update", "meetings", "meeting", "update", "Update non-finalized project meetings.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.meeting.manage", "meetings", "meeting", "manage", "Cancel and administratively manage project meetings.", PermissionRisk.HIGH),
    ModulePermissionDefinition("meetings.series.manage", "meetings", "series", "manage", "Create and manage recurring meeting series.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.attendee.manage", "meetings", "attendee", "manage", "Manage meeting attendees and attendance.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.agenda.manage", "meetings", "agenda", "manage", "Manage meeting agenda items.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.action.view", "meetings", "action", "view", "View assigned and project meeting action items.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.action.manage", "meetings", "action", "manage", "Create, assign and update meeting action items.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.reference.manage", "meetings", "reference", "manage", "Link permitted project records to meetings.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.minutes.manage", "meetings", "minutes", "manage", "Draft and revise meeting minutes before finalization.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("meetings.minutes.finalize", "meetings", "minutes", "finalize", "Finalize meeting minutes under configured approval rules.", PermissionRisk.HIGH),
    ModulePermissionDefinition("help.assistant.use", "help", "assistant", "use", "Use the permission-scoped Construction OS Assistant.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("help.assistant.upgrade", "help", "assistant", "upgrade_guidance", "Use installation, upgrade, migration and rollback guidance from the Construction OS Assistant.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.module.view", "commercial", "module", "view", "Access India commercial controls within authorized projects.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("commercial.party.view", "commercial", "party", "view", "View company parties and project party assignments.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("commercial.party.manage", "commercial", "party", "manage", "Create and maintain parties and project party assignments.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.wbs.view", "commercial", "wbs", "view", "View project WBS and cost-code structures.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("commercial.wbs.manage", "commercial", "wbs", "manage", "Create and revise project WBS and cost-code structures.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.boq.view", "commercial", "boq", "view", "View BOQs and approved commercial baselines.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.boq.manage", "commercial", "boq", "manage", "Create and revise draft BOQs and BOQ items.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.boq.approve", "commercial", "boq", "approve", "Approve a BOQ baseline and create an immutable snapshot.", PermissionRisk.CRITICAL),
    ModulePermissionDefinition("commercial.measurement.view", "commercial", "measurement", "view", "View project measurement-book entries.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.measurement.create", "commercial", "measurement", "create", "Record project quantities against approved BOQ items.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.measurement.submit", "commercial", "measurement", "submit", "Submit measured quantities for certification.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.measurement.certify", "commercial", "measurement", "certify", "Certify or reject submitted measured quantities.", PermissionRisk.CRITICAL),
    ModulePermissionDefinition("commercial.ra_bill.view", "commercial", "ra_bill", "view", "View RA bills and their certified measurement basis.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.ra_bill.create", "commercial", "ra_bill", "create", "Prepare RA bills from unbilled certified measurements.", PermissionRisk.HIGH),
    ModulePermissionDefinition("commercial.ra_bill.submit", "commercial", "ra_bill", "submit", "Submit an RA bill for certification.", PermissionRisk.CRITICAL),
    ModulePermissionDefinition("commercial.ra_bill.certify", "commercial", "ra_bill", "certify", "Certify RA bills and record payment state transitions.", PermissionRisk.CRITICAL),
    ModulePermissionDefinition("estimating.module.view", "estimating", "module", "view", "Access estimating and budget controls.", PermissionRisk.MEDIUM),
    ModulePermissionDefinition("estimating.estimate.view", "estimating", "estimate", "view", "View project estimates and rate analyses.", PermissionRisk.HIGH),
    ModulePermissionDefinition("estimating.estimate.manage", "estimating", "estimate", "manage", "Create and revise draft estimates.", PermissionRisk.HIGH),
    ModulePermissionDefinition("estimating.estimate.submit", "estimating", "estimate", "submit", "Submit project estimates for approval.", PermissionRisk.HIGH),
    ModulePermissionDefinition("estimating.estimate.approve", "estimating", "estimate", "approve", "Approve project estimates.", PermissionRisk.CRITICAL),
    ModulePermissionDefinition("estimating.rate_analysis.manage", "estimating", "rate_analysis", "manage", "Create versioned rate analyses.", PermissionRisk.HIGH),
    ModulePermissionDefinition("estimating.budget.view", "estimating", "budget", "view", "View project budget baselines.", PermissionRisk.HIGH),
    ModulePermissionDefinition("estimating.budget.manage", "estimating", "budget", "manage", "Create and revise draft project budgets.", PermissionRisk.HIGH),
    ModulePermissionDefinition("estimating.budget.approve", "estimating", "budget", "approve", "Approve a project budget baseline.", PermissionRisk.CRITICAL),
)
