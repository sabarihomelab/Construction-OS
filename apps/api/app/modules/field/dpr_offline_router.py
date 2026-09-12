from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.field.dpr_jobs import enqueue_dpr_approval_report
from app.modules.field.dpr_offline_schemas import (
    DailyReportOfflineMutationRequest,
    DailyReportOfflineMutationResponse,
    DailyReportOfflineOperation,
)
from app.modules.field.dpr_schemas import DPRWorkProgressRead
from app.modules.field.dpr_service import (
    DPRConflictError,
    DPRValidationError,
    list_work_progress,
    replace_work_progress,
)
from app.modules.field.models import DailyReport, DailyReportDelayEntry
from app.modules.field.router import _require_permission
from app.modules.field.schemas import DailyReportRead, DelayEntryRead
from app.modules.field.service import (
    DailyReportConflictError,
    DailyReportValidationError,
    create_daily_report,
    replace_daily_report_sections,
    submit_daily_report,
    update_daily_report,
)
from app.modules.offline.models import (
    SyncMutationOperation,
    SyncMutationReceipt,
    SyncMutationStatus,
)
from app.modules.offline.service import (
    IdempotencyConflictError,
    OfflineSyncError,
    begin_mutation,
    mark_mutation_applied,
    mark_mutation_conflict,
    mark_mutation_rejected,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["daily-reports-offline"])

_ENTITY_TYPE = "daily_report"


def _permission_for(operation: DailyReportOfflineOperation) -> str:
    if operation == DailyReportOfflineOperation.CREATE_REPORT:
        return "field.daily_report.create"
    if operation in {
        DailyReportOfflineOperation.UPDATE_HEADER,
        DailyReportOfflineOperation.REPLACE_WORK_PROGRESS,
        DailyReportOfflineOperation.REPLACE_DELAYS,
    }:
        return "field.daily_report.update"
    return "field.daily_report.submit"


def _sync_operation(operation: DailyReportOfflineOperation) -> SyncMutationOperation:
    if operation == DailyReportOfflineOperation.CREATE_REPORT:
        return SyncMutationOperation.CREATE
    if operation in {
        DailyReportOfflineOperation.UPDATE_HEADER,
        DailyReportOfflineOperation.REPLACE_WORK_PROGRESS,
        DailyReportOfflineOperation.REPLACE_DELAYS,
    }:
        return SyncMutationOperation.UPDATE
    return SyncMutationOperation.ACTION


def _receipt_response(
    receipt: SyncMutationReceipt,
    *,
    replayed: bool,
) -> DailyReportOfflineMutationResponse:
    if receipt.entity_id is None:
        raise RuntimeError("Daily Report mutation receipt is missing its entity ID")
    return DailyReportOfflineMutationResponse(
        client_mutation_id=receipt.client_mutation_id,
        entity_id=UUID(receipt.entity_id),
        status=receipt.status,
        replayed=replayed,
        server_revision=receipt.server_version,
        result=receipt.result,
        error_code=receipt.error_code,
    )


def _response_status(receipt: SyncMutationReceipt) -> int:
    if receipt.status == SyncMutationStatus.APPLIED:
        return status.HTTP_200_OK
    if receipt.status == SyncMutationStatus.CONFLICT:
        return status.HTTP_409_CONFLICT
    if receipt.status == SyncMutationStatus.REJECTED:
        if receipt.error_code == "domain_conflict":
            return status.HTTP_409_CONFLICT
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    return status.HTTP_409_CONFLICT


def _json_response(receipt: SyncMutationReceipt, *, replayed: bool) -> JSONResponse:
    body = _receipt_response(receipt, replayed=replayed)
    return JSONResponse(
        status_code=_response_status(receipt),
        content=body.model_dump(mode="json"),
    )


def _request_payload(
    project_id: UUID,
    payload: DailyReportOfflineMutationRequest,
) -> dict[str, object]:
    return {
        "project_id": str(project_id),
        "mutation": payload.model_dump(mode="json"),
    }


def _client_conflict_payload(payload: DailyReportOfflineMutationRequest) -> dict[str, object]:
    return payload.model_dump(mode="json")


async def _current_report(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    report_id: UUID,
) -> DailyReport | None:
    return await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.organization_id == organization_id,
            DailyReport.project_id == project_id,
        )
    )


def _report_result(report: DailyReport) -> dict[str, object]:
    return {
        "report": DailyReportRead.model_validate(report).model_dump(mode="json"),
    }


async def _operation_result(
    db: DbSession,
    *,
    operation: DailyReportOfflineOperation,
    report: DailyReport,
    organization_id: UUID,
    project_id: UUID,
) -> dict[str, object]:
    result = _report_result(report)
    if operation == DailyReportOfflineOperation.REPLACE_WORK_PROGRESS:
        rows = await list_work_progress(
            db,
            organization_id=organization_id,
            project_id=project_id,
            report_id=report.id,
        )
        result["work_progress"] = [
            DPRWorkProgressRead.model_validate(row).model_dump(mode="json") for row in rows
        ]
    elif operation == DailyReportOfflineOperation.REPLACE_DELAYS:
        rows = await db.scalars(
            select(DailyReportDelayEntry)
            .where(
                DailyReportDelayEntry.organization_id == organization_id,
                DailyReportDelayEntry.daily_report_id == report.id,
            )
            .order_by(DailyReportDelayEntry.created_at, DailyReportDelayEntry.id)
        )
        result["delays"] = [
            DelayEntryRead.model_validate(row).model_dump(mode="json") for row in rows.all()
        ]
    return result


async def _apply_operation(
    db: DbSession,
    *,
    project_id: UUID,
    payload: DailyReportOfflineMutationRequest,
    organization_id: UUID,
    membership_id: UUID,
    user_id: UUID,
    session_id: UUID,
) -> DailyReport:
    if payload.operation == DailyReportOfflineOperation.CREATE_REPORT:
        create = payload.create
        if create is None:
            raise DailyReportValidationError("Daily Report create payload is required")
        return await create_daily_report(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=membership_id,
            actor_user_id=user_id,
            values=create.model_dump(),
            session_id=session_id,
        )

    if payload.operation == DailyReportOfflineOperation.UPDATE_HEADER:
        update = payload.update
        if update is None:
            raise DailyReportValidationError("Daily Report update payload is required")
        return await update_daily_report(
            db,
            organization_id=organization_id,
            project_id=project_id,
            report_id=payload.entity_id,
            expected_revision=update.expected_revision,
            changes=update.model_dump(
                exclude={"expected_revision", "reason"},
                exclude_unset=True,
            ),
            actor_user_id=user_id,
            session_id=session_id,
            reason=update.reason,
        )

    if payload.operation == DailyReportOfflineOperation.REPLACE_WORK_PROGRESS:
        work_progress = payload.work_progress
        if work_progress is None:
            raise DPRValidationError("DPR work progress payload is required")
        return await replace_work_progress(
            db,
            organization_id=organization_id,
            project_id=project_id,
            report_id=payload.entity_id,
            expected_revision=work_progress.expected_revision,
            rows=work_progress.rows,
            actor_user_id=user_id,
            session_id=session_id,
            reason=work_progress.reason,
        )

    if payload.operation == DailyReportOfflineOperation.REPLACE_DELAYS:
        delays = payload.delays
        if delays is None:
            raise DailyReportValidationError("DPR delays payload is required")
        return await replace_daily_report_sections(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=membership_id,
            report_id=payload.entity_id,
            expected_revision=delays.expected_revision,
            sections={"delays": [row.model_dump() for row in delays.rows]},
            actor_user_id=user_id,
            session_id=session_id,
            reason=delays.reason,
        )

    action = payload.action
    if action is None:
        raise DailyReportValidationError("Daily Report submit payload is required")
    report = await submit_daily_report(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
        report_id=payload.entity_id,
        expected_revision=action.expected_revision,
        actor_user_id=user_id,
        session_id=session_id,
        reason=action.reason,
    )
    await enqueue_dpr_approval_report(
        db,
        report=report,
        actor_user_id=user_id,
        session_id=session_id,
    )
    return report


@router.post(
    "/projects/{project_id}/daily-reports/offline/mutations",
    response_model=DailyReportOfflineMutationResponse,
    responses={409: {"model": DailyReportOfflineMutationResponse}},
)
async def apply_daily_report_offline_mutation(
    project_id: UUID,
    payload: DailyReportOfflineMutationRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> JSONResponse:
    context = await build_access_context(db, session.membership_id)
    _require_permission(context, project_id, _permission_for(payload.operation))

    try:
        receipt, replayed = await begin_mutation(
            db,
            organization_id=context.organization_id,
            user_id=session.user_id,
            device_id=payload.device_id,
            client_mutation_id=payload.client_mutation_id,
            entity_type=_ENTITY_TYPE,
            entity_id=payload.entity_id,
            operation=_sync_operation(payload.operation),
            request_payload=_request_payload(project_id, payload),
            base_version=payload.base_revision,
        )
    except IdempotencyConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except OfflineSyncError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if replayed:
        return _json_response(receipt, replayed=True)

    try:
        try:
            async with db.begin_nested():
                report = await _apply_operation(
                    db,
                    project_id=project_id,
                    payload=payload,
                    organization_id=context.organization_id,
                    membership_id=context.membership_id,
                    user_id=session.user_id,
                    session_id=session.id,
                )
        except (DailyReportConflictError, DPRConflictError) as exc:
            current = await _current_report(
                db,
                organization_id=context.organization_id,
                project_id=project_id,
                report_id=payload.entity_id,
            )
            if (
                current is not None
                and payload.base_revision is not None
                and current.revision != payload.base_revision
            ):
                server_result = _report_result(current)
                await mark_mutation_conflict(
                    db,
                    receipt,
                    entity_id=current.id,
                    base_version=payload.base_revision,
                    server_version=current.revision,
                    client_patch=_client_conflict_payload(payload),
                    server_values=server_result,
                    result=server_result,
                )
            else:
                await mark_mutation_rejected(
                    db,
                    receipt,
                    error_code="domain_conflict",
                    result={"detail": str(exc)},
                )
        except (DailyReportValidationError, DPRValidationError) as exc:
            await mark_mutation_rejected(
                db,
                receipt,
                error_code="validation_error",
                result={"detail": str(exc)},
            )
        else:
            receipt.entity_id = str(report.id)
            await mark_mutation_applied(
                db,
                receipt,
                server_version=report.revision,
                result=await _operation_result(
                    db,
                    operation=payload.operation,
                    report=report,
                    organization_id=context.organization_id,
                    project_id=project_id,
                ),
            )
        await db.commit()
        return _json_response(receipt, replayed=False)
    except OfflineSyncError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        await db.rollback()
        raise
