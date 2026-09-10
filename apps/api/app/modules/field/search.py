from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field.models import DailyReport, DailyReportDelayEntry, DailyReportWorkEntry
from app.modules.search.providers import search_projection_providers
from app.modules.search.schemas import SearchProjection


async def daily_report_search_projection(
    db: AsyncSession,
    organization_id: UUID,
    entity_id: str,
) -> SearchProjection | None:
    try:
        report_id = UUID(entity_id)
    except ValueError:
        return None

    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
        )
    )
    if report is None:
        return None

    work_rows = await db.scalars(
        select(DailyReportWorkEntry.description)
        .where(
            DailyReportWorkEntry.organization_id == organization_id,
            DailyReportWorkEntry.daily_report_id == report.id,
        )
        .order_by(DailyReportWorkEntry.created_at)
        .limit(20)
    )
    delay_rows = await db.scalars(
        select(DailyReportDelayEntry.description)
        .where(
            DailyReportDelayEntry.organization_id == organization_id,
            DailyReportDelayEntry.daily_report_id == report.id,
        )
        .order_by(DailyReportDelayEntry.created_at)
        .limit(10)
    )

    body_parts: list[str] = []
    if report.weather_condition:
        body_parts.append(report.weather_condition)
    if report.notes:
        body_parts.append(report.notes)
    body_parts.extend(work_rows.all())
    body_parts.extend(delay_rows.all())

    title = f"Daily Report {report.report_date.isoformat()}"
    return SearchProjection(
        entity_type="daily_report",
        entity_id=str(report.id),
        entity_version=report.revision,
        required_permission_key="field.daily_report.view",
        scope_type="project",
        scope_id=str(report.project_id),
        title=title,
        subtitle=f"{report.shift_code} · {report.status.value}",
        body="\n".join(body_parts),
        keywords=[title, report.shift_code, report.status.value],
        route_hint=f"/projects/{report.project_id}/daily-reports/{report.id}",
        source_updated_at=report.updated_at,
    )


if not search_projection_providers.contains("daily_report"):
    search_projection_providers.register("daily_report", daily_report_search_projection)
