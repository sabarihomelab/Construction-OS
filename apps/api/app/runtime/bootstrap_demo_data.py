import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.commercial.models import (
    BOQ,
    BOQItem,
    BOQStatus,
    Party,
    PartyStatus,
    PartyType,
    ProjectPartyAssignment,
    ProjectPartyRole,
    RecordStatus,
    WBSCode,
    WBSKind,
)
from app.modules.estimating.models import (
    BudgetCategory,
    BudgetLine,
    BudgetStatus,
    EstimateItem,
    EstimateStatus,
    ProjectBudget,
    ProjectEstimate,
)
from app.modules.field.dpr_models import DPRWorkProgressEntry, DPRWorkProgressSourceType
from app.modules.field.models import (
    DailyReport,
    DailyReportDelayEntry,
    DailyReportHistoryEvent,
    DailyReportHistoryType,
    DailyReportStatus,
)
from app.modules.identity.models import MembershipStatus, OrganizationMembership, User
from app.modules.metadata.models import (
    CustomFieldDefinition,
    CustomFieldOption,
    CustomFieldType,
    CustomFieldValue,
)
from app.modules.organizations.models import Organization
from app.modules.projects.models import (
    Project,
    ProjectMembership,
    ProjectMembershipStatus,
    ProjectStatus,
)
from app.modules.workforce.attendance_models import (
    AttendanceEntry,
    AttendanceHistoryEvent,
    AttendanceHistoryType,
    AttendanceMarkStatus,
    AttendanceRegister,
    AttendanceRegisterStatus,
)
from app.modules.workforce.models import (
    Crew,
    CrewMembership,
    CrewStatus,
    EmploymentStatus,
    ProjectWorkerAssignment,
    ProjectWorkerAssignmentStatus,
    Worker,
    WorkerEngagementType,
)

DEMO_PROJECT_NUMBER = "DEMO-001"
DEMO_PROJECT_NAME = "Riverside Residency - Phase 1"


class DemoDataBootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DemoDataBootstrapResult:
    status: str
    organization_id: str
    project_id: str
    project_number: str
    project_name: str
    parties: int
    wbs_codes: int
    boq_items: int
    estimates: int
    budgets: int
    crews: int
    workers: int
    approved_attendance_days: int
    daily_reports: int
    custom_fields: int


def ensure_demo_environment(environment: str) -> None:
    if environment.strip().lower() not in {"development", "test"}:
        raise DemoDataBootstrapError(
            "Demo data bootstrap is allowed only in development or test environments"
        )


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


async def _admin_context(
    db: AsyncSession,
    *,
    admin_email: str,
) -> tuple[User, OrganizationMembership, Organization]:
    rows = (
        await db.execute(
            select(User, OrganizationMembership, Organization)
            .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
            .join(Organization, Organization.id == OrganizationMembership.organization_id)
            .where(
                func.lower(User.primary_email) == admin_email.strip().lower(),
                User.is_active.is_(True),
                OrganizationMembership.status == MembershipStatus.ACTIVE,
                Organization.is_active.is_(True),
            )
            .order_by(Organization.name, OrganizationMembership.id)
        )
    ).all()
    deployment_org = get_settings().deployment_organization_id
    if deployment_org is not None:
        rows = [row for row in rows if row[1].organization_id == deployment_org]
    if not rows:
        raise DemoDataBootstrapError(
            "Active administrator membership was not found; run bootstrap-company.ps1 first"
        )
    if len(rows) > 1:
        raise DemoDataBootstrapError(
            "Administrator belongs to multiple companies; bind this development deployment "
            "to one company before seeding demo data"
        )
    return rows[0]


async def _count(db: AsyncSession, model, *conditions) -> int:
    value = await db.scalar(select(func.count()).select_from(model).where(*conditions))
    return int(value or 0)


async def _existing_result(
    db: AsyncSession,
    *,
    organization_id,
    project: Project,
) -> DemoDataBootstrapResult:
    crew_count = await db.scalar(
        select(func.count(func.distinct(ProjectWorkerAssignment.crew_id))).where(
            ProjectWorkerAssignment.project_id == project.id,
            ProjectWorkerAssignment.crew_id.is_not(None),
        )
    )
    return DemoDataBootstrapResult(
        status="exists",
        organization_id=str(organization_id),
        project_id=str(project.id),
        project_number=project.number,
        project_name=project.name,
        parties=await _count(
            db,
            ProjectPartyAssignment,
            ProjectPartyAssignment.project_id == project.id,
        ),
        wbs_codes=await _count(db, WBSCode, WBSCode.project_id == project.id),
        boq_items=await _count(db, BOQItem, BOQItem.project_id == project.id),
        estimates=await _count(db, ProjectEstimate, ProjectEstimate.project_id == project.id),
        budgets=await _count(db, ProjectBudget, ProjectBudget.project_id == project.id),
        crews=int(crew_count or 0),
        workers=await _count(
            db,
            ProjectWorkerAssignment,
            ProjectWorkerAssignment.project_id == project.id,
        ),
        approved_attendance_days=await _count(
            db,
            AttendanceRegister,
            AttendanceRegister.project_id == project.id,
            AttendanceRegister.status == AttendanceRegisterStatus.APPROVED,
        ),
        daily_reports=await _count(db, DailyReport, DailyReport.project_id == project.id),
        custom_fields=await _count(
            db,
            CustomFieldDefinition,
            CustomFieldDefinition.organization_id == organization_id,
            CustomFieldDefinition.entity_type == "daily_report",
            CustomFieldDefinition.key.like("demo_%"),
        ),
    )


async def seed_demo_data(
    db: AsyncSession,
    *,
    admin_email: str,
    project_number: str = DEMO_PROJECT_NUMBER,
    project_name: str = DEMO_PROJECT_NAME,
) -> DemoDataBootstrapResult:
    settings = get_settings()
    ensure_demo_environment(settings.environment)
    user, membership, organization = await _admin_context(db, admin_email=admin_email)

    existing = await db.scalar(
        select(Project).where(
            Project.organization_id == organization.id,
            Project.number == project_number,
        )
    )
    if existing is not None:
        return await _existing_result(
            db,
            organization_id=organization.id,
            project=existing,
        )

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    now = datetime.now(UTC)
    project = Project(
        organization_id=organization.id,
        number=project_number,
        name=project_name,
        description=(
            "Development-only apartment construction project seeded for Android Modules 1-6 "
            "self-testing."
        ),
        status=ProjectStatus.ACTIVE,
        timezone="Asia/Kolkata",
        currency_code="INR",
        unit_system="metric",
        start_date=today - timedelta(days=120),
        target_completion_date=today + timedelta(days=300),
        address_line_1="Avinashi Road",
        locality="Coimbatore",
        region="Tamil Nadu",
        postal_code="641014",
        country_code="IN",
    )
    db.add(project)
    await db.flush()
    db.add(
        ProjectMembership(
            organization_id=organization.id,
            project_id=project.id,
            organization_membership_id=membership.id,
            status=ProjectMembershipStatus.ACTIVE,
            title="Company Administrator",
        )
    )

    party_specs = [
        ("DEMO-CLIENT", "Greenfield Developers Pvt Ltd", PartyType.CLIENT, ProjectPartyRole.CLIENT),
        (
            "DEMO-CONSULT",
            "Axis Design Consultants",
            PartyType.CONSULTANT,
            ProjectPartyRole.CONSULTANT,
        ),
        (
            "DEMO-LABOUR",
            "Sri Velan Labour Contractors",
            PartyType.LABOUR_CONTRACTOR,
            ProjectPartyRole.LABOUR_CONTRACTOR,
        ),
        ("DEMO-SUPPLIER", "Kovai BuildMart", PartyType.SUPPLIER, ProjectPartyRole.SUPPLIER),
        (
            "DEMO-MEP",
            "Apex MEP Services",
            PartyType.SUBCONTRACTOR,
            ProjectPartyRole.SUBCONTRACTOR,
        ),
    ]
    parties: dict[str, Party] = {}
    for code, name, party_type, role in party_specs:
        party = Party(
            organization_id=organization.id,
            code=code,
            name=name,
            legal_name=name,
            party_type=party_type,
            status=PartyStatus.ACTIVE,
            email=f"{code.lower()}@demo.constructionos.local",
            phone="+91 90000 00000",
            locality="Coimbatore",
            state_name="Tamil Nadu",
            state_code="33",
            postal_code="641001",
            payment_terms_days=30,
            notes="Development demo party",
        )
        db.add(party)
        await db.flush()
        parties[code] = party
        db.add(
            ProjectPartyAssignment(
                organization_id=organization.id,
                project_id=project.id,
                party_id=party.id,
                role=role,
                active=True,
            )
        )

    wbs_specs = [
        ("01", "Preliminaries", WBSKind.GROUP, None),
        ("01.01", "Site setup", WBSKind.COST_CODE, "01"),
        ("02", "Substructure", WBSKind.GROUP, None),
        ("02.01", "Earthwork", WBSKind.COST_CODE, "02"),
        ("02.02", "PCC and blinding", WBSKind.COST_CODE, "02"),
        ("02.03", "Footings and foundations", WBSKind.COST_CODE, "02"),
        ("03", "Superstructure", WBSKind.GROUP, None),
        ("03.01", "RCC frame", WBSKind.COST_CODE, "03"),
        ("03.02", "Reinforcement steel", WBSKind.COST_CODE, "03"),
        ("03.03", "Block masonry", WBSKind.COST_CODE, "03"),
        ("04", "Finishes", WBSKind.GROUP, None),
        ("04.01", "Internal plaster", WBSKind.COST_CODE, "04"),
        ("04.02", "Flooring", WBSKind.COST_CODE, "04"),
        ("04.03", "Painting", WBSKind.COST_CODE, "04"),
        ("05", "MEP", WBSKind.GROUP, None),
        ("05.01", "Electrical", WBSKind.COST_CODE, "05"),
        ("05.02", "Plumbing", WBSKind.COST_CODE, "05"),
        ("06", "External works", WBSKind.GROUP, None),
        ("06.01", "Paving and drainage", WBSKind.COST_CODE, "06"),
    ]
    wbs: dict[str, WBSCode] = {}
    for code, name, kind, parent_code in wbs_specs:
        row = WBSCode(
            organization_id=organization.id,
            project_id=project.id,
            parent_id=wbs[parent_code].id if parent_code else None,
            code=code,
            name=name,
            kind=kind,
            status=RecordStatus.ACTIVE,
            description=f"Demo WBS: {name}",
        )
        db.add(row)
        await db.flush()
        wbs[code] = row

    boq = BOQ(
        organization_id=organization.id,
        project_id=project.id,
        code="BOQ-DEMO-01",
        name="Riverside Residency Approved BOQ",
        description="Approved demo BOQ for Android field lookup and DPR work progress.",
        currency_code="INR",
        status=BOQStatus.APPROVED,
        revision=2,
        approved_by_membership_id=membership.id,
        approved_at=now - timedelta(days=30),
    )
    db.add(boq)
    await db.flush()

    boq_specs = [
        ("01.01", "Mobilisation and temporary facilities", "LS", "1", "350000"),
        ("02.01", "Excavation for foundations", "m3", "950", "310"),
        ("02.01", "Backfilling with approved material", "m3", "620", "280"),
        ("02.02", "PCC M10 below foundations", "m3", "115", "5600"),
        ("02.03", "RCC M25 in isolated footings", "m3", "210", "8200"),
        ("02.03", "Foundation shuttering", "m2", "960", "620"),
        ("03.01", "RCC M30 columns", "m3", "340", "9100"),
        ("03.01", "RCC M30 beams", "m3", "420", "9200"),
        ("03.01", "RCC M30 slabs", "m3", "610", "9000"),
        ("03.01", "Column and beam formwork", "m2", "4200", "780"),
        ("03.01", "Slab formwork", "m2", "5900", "690"),
        ("03.02", "Fe500D reinforcement supply and fixing", "kg", "185000", "78"),
        ("03.03", "200 mm AAC block masonry", "m2", "3100", "1250"),
        ("03.03", "100 mm AAC block masonry", "m2", "2200", "1020"),
        ("04.01", "Internal cement plaster 12 mm", "m2", "8200", "290"),
        ("04.01", "External plaster 15 mm", "m2", "3100", "360"),
        ("04.02", "Vitrified tile flooring", "m2", "4800", "1450"),
        ("04.02", "Anti-skid toilet flooring", "m2", "820", "1520"),
        ("04.02", "Granite staircase finish", "m2", "520", "3100"),
        ("04.03", "Interior wall putty and primer", "m2", "11800", "220"),
        ("04.03", "Interior acrylic emulsion paint", "m2", "11800", "260"),
        ("04.03", "Exterior weather coat paint", "m2", "4100", "330"),
        ("05.01", "Concealed electrical conduit", "m", "12500", "95"),
        ("05.01", "Copper wiring and termination", "point", "1850", "920"),
        ("05.01", "Distribution boards", "no", "48", "14500"),
        ("05.02", "CPVC water supply piping", "m", "5200", "410"),
        ("05.02", "UPVC soil and waste piping", "m", "4300", "520"),
        ("05.02", "Sanitary fixtures installation", "set", "192", "9800"),
        ("06.01", "Interlocking paver blocks", "m2", "1850", "1050"),
        ("06.01", "Storm-water drain", "m", "680", "1850"),
        ("06.01", "External kerb stones", "m", "920", "720"),
        ("06.01", "Landscape top soil and planting", "m2", "1250", "680"),
    ]
    boq_items: list[BOQItem] = []
    for line_number, (wbs_code, description, unit, quantity_raw, rate_raw) in enumerate(
        boq_specs,
        start=1,
    ):
        quantity = Decimal(quantity_raw)
        rate = Decimal(rate_raw)
        item = BOQItem(
            organization_id=organization.id,
            project_id=project.id,
            boq_id=boq.id,
            wbs_code_id=wbs[wbs_code].id,
            line_number=line_number,
            item_code=f"DEMO-{line_number:03d}",
            description=description,
            unit_code=unit,
            quantity=quantity,
            rate=rate,
            amount=_money(quantity * rate),
            notes="Development demo BOQ item",
        )
        db.add(item)
        boq_items.append(item)
    await db.flush()

    estimate = ProjectEstimate(
        organization_id=organization.id,
        project_id=project.id,
        source_boq_id=boq.id,
        code="EST-DEMO-01",
        name="Submitted Construction Estimate",
        description="Demo estimate intentionally left submitted for mobile approval testing.",
        currency_code="INR",
        status=EstimateStatus.SUBMITTED,
        revision=2,
    )
    db.add(estimate)
    await db.flush()
    for line_number, boq_item in enumerate(boq_items[:12], start=1):
        db.add(
            EstimateItem(
                organization_id=organization.id,
                project_id=project.id,
                estimate_id=estimate.id,
                wbs_code_id=boq_item.wbs_code_id,
                boq_item_id=boq_item.id,
                line_number=line_number,
                item_code=boq_item.item_code,
                description=boq_item.description,
                unit_code=boq_item.unit_code,
                quantity=boq_item.quantity,
                rate=boq_item.rate,
                amount=boq_item.amount,
                notes="Demo estimate item",
            )
        )

    budget = ProjectBudget(
        organization_id=organization.id,
        project_id=project.id,
        estimate_id=estimate.id,
        code="BUD-DEMO-01",
        name="Draft Project Control Budget",
        currency_code="INR",
        status=BudgetStatus.DRAFT,
        notes="Demo budget intentionally left draft for mobile approval testing.",
    )
    db.add(budget)
    await db.flush()
    budget_specs = [
        ("02.03", BudgetCategory.MATERIAL, "1850000"),
        ("02.03", BudgetCategory.LABOUR, "720000"),
        ("03.01", BudgetCategory.MATERIAL, "5200000"),
        ("03.01", BudgetCategory.LABOUR, "2100000"),
        ("03.02", BudgetCategory.MATERIAL, "14800000"),
        ("04.02", BudgetCategory.MATERIAL, "6900000"),
        ("05.01", BudgetCategory.SUBCONTRACT, "4850000"),
        ("05.02", BudgetCategory.SUBCONTRACT, "5350000"),
    ]
    for wbs_code, category, amount in budget_specs:
        db.add(
            BudgetLine(
                organization_id=organization.id,
                project_id=project.id,
                budget_id=budget.id,
                wbs_code_id=wbs[wbs_code].id,
                category=category,
                amount=Decimal(amount),
                notes="Demo control budget",
            )
        )

    first_names = [
        "Arun",
        "Bala",
        "Chandru",
        "Dinesh",
        "Elango",
        "Feroz",
        "Ganesh",
        "Hari",
        "Irfan",
        "Jagan",
    ]
    last_names = ["Kumar", "Murugan", "Raja", "Selvam"]
    worker_names = [(first, last) for last in last_names for first in first_names]
    crew_specs = [
        ("Civil Crew A", "Masonry", "03.03"),
        ("Steel & Formwork Crew", "Reinforcement", "03.02"),
        ("Finishing Crew", "Finishes", "04.01"),
        ("MEP Crew", "MEP", "05.01"),
    ]
    workers: list[Worker] = []
    for index, (first_name, last_name) in enumerate(worker_names, start=1):
        crew_index = (index - 1) // 10
        trade = crew_specs[crew_index][1]
        worker = Worker(
            organization_id=organization.id,
            worker_number=f"DEMO-W{index:03d}",
            first_name=first_name,
            last_name=last_name,
            phone=f"+91 90000 {index:05d}",
            job_title="Site Supervisor" if index in {1, 11, 21, 31} else trade,
            trade=trade,
            classification="Skilled" if index % 3 else "Helper",
            hire_date=today - timedelta(days=180 + index),
            status=EmploymentStatus.ACTIVE,
        )
        db.add(worker)
        workers.append(worker)
    await db.flush()

    crews: list[Crew] = []
    for crew_index, (crew_name, trade, _) in enumerate(crew_specs):
        crew = Crew(
            organization_id=organization.id,
            name=crew_name,
            description=f"Demo {trade} crew",
            supervisor_worker_id=workers[crew_index * 10].id,
            status=CrewStatus.ACTIVE,
        )
        db.add(crew)
        crews.append(crew)
    await db.flush()

    assignments: list[ProjectWorkerAssignment] = []
    for index, worker in enumerate(workers):
        crew_index = index // 10
        crew = crews[crew_index]
        wbs_code = crew_specs[crew_index][2]
        employer = parties["DEMO-MEP"] if crew_index == 3 else parties["DEMO-LABOUR"]
        db.add(
            CrewMembership(
                organization_id=organization.id,
                crew_id=crew.id,
                worker_id=worker.id,
                role="Supervisor" if index % 10 == 0 else "Member",
                effective_from=today - timedelta(days=120),
            )
        )
        assignment = ProjectWorkerAssignment(
            organization_id=organization.id,
            project_id=project.id,
            worker_id=worker.id,
            crew_id=crew.id,
            employer_party_id=employer.id,
            engagement_type=WorkerEngagementType.CONTRACT_LABOUR,
            status=ProjectWorkerAssignmentStatus.ACTIVE,
            project_role=worker.job_title,
            trade=worker.trade,
            default_cost_code=wbs_code,
            start_date=today - timedelta(days=120),
        )
        db.add(assignment)
        assignments.append(assignment)
    await db.flush()

    for day_offset in (3, 2, 1):
        attendance_date = today - timedelta(days=day_offset)
        timestamp = now - timedelta(days=day_offset)
        register = AttendanceRegister(
            organization_id=organization.id,
            project_id=project.id,
            attendance_date=attendance_date,
            shift_code="day",
            status=AttendanceRegisterStatus.APPROVED,
            revision=3,
            prepared_by_membership_id=membership.id,
            approved_by_membership_id=membership.id,
            configuration_context={"source": "demo_data"},
            notes="Approved historical demo attendance",
            submitted_at=timestamp.replace(hour=11, minute=30),
            approved_at=timestamp.replace(hour=12, minute=0),
        )
        db.add(register)
        await db.flush()
        for index, assignment in enumerate(assignments):
            if index % 17 == 0:
                mark = AttendanceMarkStatus.ABSENT
                regular_hours = Decimal(0)
                overtime_hours = Decimal(0)
            elif index % 11 == 0:
                mark = AttendanceMarkStatus.HALF_DAY
                regular_hours = Decimal(4)
                overtime_hours = Decimal(0)
            else:
                mark = AttendanceMarkStatus.PRESENT
                regular_hours = Decimal(8)
                overtime_hours = Decimal(1) if index % 5 == 0 else Decimal(0)
            crew_index = index // 10
            db.add(
                AttendanceEntry(
                    organization_id=organization.id,
                    project_id=project.id,
                    register_id=register.id,
                    assignment_id=assignment.id,
                    worker_id=assignment.worker_id,
                    crew_id=assignment.crew_id,
                    employer_party_id=assignment.employer_party_id,
                    wbs_code_id=wbs[crew_specs[crew_index][2]].id,
                    engagement_type=assignment.engagement_type,
                    trade=assignment.trade,
                    mark_status=mark,
                    regular_hours=regular_hours,
                    overtime_hours=overtime_hours,
                    location="Tower A",
                    source_type="demo",
                    context_snapshot={"seeded": True},
                )
            )
        db.add_all(
            [
                AttendanceHistoryEvent(
                    organization_id=organization.id,
                    register_id=register.id,
                    event_type=AttendanceHistoryType.CREATED,
                    register_revision=1,
                    actor_user_id=user.id,
                    details={"source": "demo_data"},
                ),
                AttendanceHistoryEvent(
                    organization_id=organization.id,
                    register_id=register.id,
                    event_type=AttendanceHistoryType.APPROVED,
                    register_revision=3,
                    actor_user_id=user.id,
                    details={"source": "demo_data"},
                ),
            ]
        )

    custom_site_condition = CustomFieldDefinition(
        organization_id=organization.id,
        entity_type="daily_report",
        key="demo_site_condition",
        label="Site condition",
        description="Overall work-area condition for the shift.",
        field_type=CustomFieldType.SINGLE_SELECT,
        required=True,
        validation_rules={},
        configuration={},
        reportable=True,
        visible=True,
        editable=True,
        display_order=10,
    )
    custom_toolbox = CustomFieldDefinition(
        organization_id=organization.id,
        entity_type="daily_report",
        key="demo_toolbox_talk",
        label="Toolbox talk completed",
        description="Record whether the daily toolbox talk was completed.",
        field_type=CustomFieldType.BOOLEAN,
        required=False,
        validation_rules={},
        configuration={},
        reportable=True,
        visible=True,
        editable=True,
        display_order=20,
    )
    custom_notes = CustomFieldDefinition(
        organization_id=organization.id,
        entity_type="daily_report",
        key="demo_visitor_notes",
        label="Visitor / inspection notes",
        field_type=CustomFieldType.LONG_TEXT,
        required=False,
        validation_rules={},
        configuration={},
        reportable=True,
        visible=True,
        editable=True,
        display_order=30,
    )
    db.add_all([custom_site_condition, custom_toolbox, custom_notes])
    await db.flush()
    for order, (key, label) in enumerate(
        [("normal", "Normal"), ("wet", "Wet / muddy"), ("restricted", "Restricted access")],
        start=1,
    ):
        db.add(
            CustomFieldOption(
                definition_id=custom_site_condition.id,
                key=key,
                label=label,
                display_order=order * 10,
            )
        )

    report_specs = [
        (
            today - timedelta(days=2),
            DailyReportStatus.REJECTED,
            3,
            "Clear",
            "Demo report rejected so reopen behavior can be tested.",
        ),
        (
            today - timedelta(days=1),
            DailyReportStatus.DRAFT,
            2,
            "Partly cloudy",
            "Demo draft with work progress and a delivery-access delay.",
        ),
    ]
    reports: list[DailyReport] = []
    for report_date, status, revision, weather, notes in report_specs:
        report = DailyReport(
            organization_id=organization.id,
            project_id=project.id,
            report_date=report_date,
            shift_code="day",
            status=status,
            revision=revision,
            prepared_by_membership_id=membership.id,
            weather_condition=weather,
            temperature_low=Decimal(24),
            temperature_high=Decimal(32),
            temperature_unit="C",
            notes=notes,
            configuration_context={"source": "demo_data"},
            submitted_at=(now - timedelta(days=2, hours=2))
            if status == DailyReportStatus.REJECTED
            else None,
            rejected_at=(now - timedelta(days=2)) if status == DailyReportStatus.REJECTED else None,
            created_by_user_id=user.id,
        )
        db.add(report)
        await db.flush()
        reports.append(report)
        db.add(
            DailyReportHistoryEvent(
                organization_id=organization.id,
                daily_report_id=report.id,
                event_type=(
                    DailyReportHistoryType.REJECTED
                    if status == DailyReportStatus.REJECTED
                    else DailyReportHistoryType.UPDATED
                ),
                report_revision=revision,
                actor_user_id=user.id,
                details={"source": "demo_data"},
            )
        )
        for item_index, boq_item in enumerate(boq_items[7:9], start=1):
            db.add(
                DPRWorkProgressEntry(
                    organization_id=organization.id,
                    project_id=project.id,
                    daily_report_id=report.id,
                    wbs_code_id=boq_item.wbs_code_id,
                    boq_item_id=boq_item.id,
                    description=boq_item.description,
                    location=f"Tower A - Level {item_index + 2}",
                    quantity=Decimal("18.5") * item_index,
                    unit_code=boq_item.unit_code,
                    progress_percent=Decimal(55) + Decimal(item_index * 10),
                    source_type=DPRWorkProgressSourceType.MANUAL,
                    remarks="Seeded work-progress entry",
                )
            )
        db.add_all(
            [
                CustomFieldValue(
                    organization_id=organization.id,
                    definition_id=custom_site_condition.id,
                    entity_id=report.id,
                    definition_version=1,
                    text_value="normal",
                    updated_by_user_id=user.id,
                ),
                CustomFieldValue(
                    organization_id=organization.id,
                    definition_id=custom_toolbox.id,
                    entity_id=report.id,
                    definition_version=1,
                    boolean_value=True,
                    updated_by_user_id=user.id,
                ),
            ]
        )

    db.add(
        DailyReportDelayEntry(
            organization_id=organization.id,
            daily_report_id=reports[-1].id,
            category="Delivery",
            description="Reinforcement truck delayed at site access gate.",
            lost_hours=Decimal("1.5"),
            responsible_party="Logistics vendor",
            schedule_impact=False,
            notes="Demo blocker for mobile editing.",
        )
    )

    await db.flush()
    return DemoDataBootstrapResult(
        status="created",
        organization_id=str(organization.id),
        project_id=str(project.id),
        project_number=project.number,
        project_name=project.name,
        parties=len(party_specs),
        wbs_codes=len(wbs_specs),
        boq_items=len(boq_items),
        estimates=1,
        budgets=1,
        crews=len(crews),
        workers=len(workers),
        approved_attendance_days=3,
        daily_reports=len(reports),
        custom_fields=3,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed realistic development-only data for Construction OS Android self-testing."
    )
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--project-number", default=DEMO_PROJECT_NUMBER)
    parser.add_argument("--project-name", default=DEMO_PROJECT_NAME)
    return parser


async def _run(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        try:
            result = await seed_demo_data(
                db,
                admin_email=args.admin_email,
                project_number=args.project_number.strip().upper(),
                project_name=args.project_name.strip(),
            )
            await db.commit()
        except DemoDataBootstrapError as exc:
            await db.rollback()
            print(json.dumps({"status": "error", "detail": str(exc)}))
            return 2
        except Exception:
            await db.rollback()
            raise
        print(json.dumps(asdict(result), sort_keys=True))
        return 0


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
