from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.field.models import ApprovalStatus, DailyLog, TimeEntry
from app.modules.field.schemas import DailyLogCreate, DailyLogRead, TimeEntryCreate, TimeEntryRead

router = APIRouter(prefix="/field", tags=["field"])


@router.get("/time-entries", response_model=list[TimeEntryRead])
async def list_time_entries(db: DbSession):
    result = await db.execute(select(TimeEntry).order_by(TimeEntry.work_date.desc()))
    return list(result.scalars())


@router.post("/time-entries", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
async def create_time_entry(payload: TimeEntryCreate, db: DbSession):
    entry = TimeEntry(**payload.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.post("/time-entries/{entry_id}/submit", response_model=TimeEntryRead)
async def submit_time_entry(entry_id: str, db: DbSession):
    entry = await db.get(TimeEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Time entry not found")
    entry.status = ApprovalStatus.SUBMITTED
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/daily-logs", response_model=list[DailyLogRead])
async def list_daily_logs(db: DbSession):
    result = await db.execute(select(DailyLog).order_by(DailyLog.report_date.desc()))
    return list(result.scalars())


@router.post("/daily-logs", response_model=DailyLogRead, status_code=status.HTTP_201_CREATED)
async def create_daily_log(payload: DailyLogCreate, db: DbSession):
    daily_log = DailyLog(**payload.model_dump())
    db.add(daily_log)
    await db.commit()
    await db.refresh(daily_log)
    return daily_log


@router.post("/daily-logs/{log_id}/submit", response_model=DailyLogRead)
async def submit_daily_log(log_id: str, db: DbSession):
    daily_log = await db.get(DailyLog, log_id)
    if daily_log is None:
        raise HTTPException(status_code=404, detail="Daily log not found")
    daily_log.status = ApprovalStatus.SUBMITTED
    await db.commit()
    await db.refresh(daily_log)
    return daily_log
