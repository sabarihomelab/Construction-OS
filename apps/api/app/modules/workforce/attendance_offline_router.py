from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.deps import DbSession
from app.modules.features.service import build_access_context
from app.modules.offline.models import SyncMutationOperation, SyncMutationReceipt, SyncMutationStatus
from app.modules.offline.service import (
    IdempotencyConflictError,
    OfflineSyncError,
    begin_mutation,
    mark_mutation_applied,
    mark_mutation_conflict,
    mark_mutation_rejected,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession
from app.modules.workforce.attendance_models import AttendanceRegister
from app.modules.workforce.attendance_router import _require_project_permission
from app.modules.workforce.attendance_schemas import (
    AttendanceOfflineMutationRequest,
    AttendanceOfflineMutationResponse,
    AttendanceOfflineOperation,
    AttendanceRegisterRead,
)
from app.modules.workforce.attendance_service import (
    create_attendance_register,
    replace_attendance_entries,
    submit_attendance,
)
from app.modules.workforce.service import WorkforceConflictError, WorkforceValidationError

router = APIRouter(tags=["workforce-attendance-offline"])

_ENTITY_TYPE = "attendance_register"


def _permission_for(operation: AttendanceOfflineOperation) -> str:
    if operation == AttendanceOfflineOperation.CREATE_REGISTER:
        return "workforce.attendance.create"
    if operation == AttendanceOfflineOperation.REPLACE_ENTRIES:
        return "workforce.attendance.update"
    return "workforce.attendance.submit"


def _sync_operation(operation: AttendanceOfflineOperation) -> SyncMutationOperation:
    if operation == AttendanceOfflineOperation.CREATE_REGISTER:
        return SyncMutationOperation.CREATE
    if operation == AttendanceOfflineOperation.REPLACE_ENTRIES:
        return SyncMutationOperation.UPDATE
    return SyncMutationOperation.ACTION


def _receipt_response(
    receipt: SyncMutationReceipt,
    *,
    replayed: bool,
) -> AttendanceOfflineMutationResponse:
    if receipt.entity_id is None:
        raise RuntimeError("Attendance mutation receipt is missing its entity ID")
    return AttendanceOfflineMutationResponse(
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
    payload: AttendanceOfflineMutationRequest,
) -> dict[str, object]:
    return {
        "project_id": str(project_id),
        "mutation": payload.model_dump(mode="json"),
    }


def _client_conflict_payload(payload: AttendanceOfflineMutationRequest) -> dict[str, object]:
    full = payload.model_dump(mode="json")
    if payload.entries is None:
        return full
    return {
        "device_id": str(payload.device_id),
        "client_mutation_id": str(payload.client_mutation_id),
        "entity_id": str(payload.entity_id),
        "operation": payload.operation.value,
        "base_revision": payload.base_revision,
        "entry_count": len(payload.entries.entries),
        "reason": payload.entries.reason,
    }


async def _current_register(
    db: DbSession,
    *,
    organization_id: UUID,
    project_id: UUID,
    register_id: UUID,
) -> AttendanceRegister | None:
    return await db.scalar(
        select(AttendanceRegister).where(
            AttendanceRegister.id == register_id,
            AttendanceRegister.organization_id == organization_id,
            AttendanceRegister.project_id == project_id,
        )
    )


def _register_result(register: AttendanceRegister) -> dict[str, object]:
    return {
        "register": AttendanceRegisterRead.model_validate(register).model_dump(mode="json"),
    }


async def _apply_operation(
    db: DbSession,
    *,
    project_id: UUID,
    payload: AttendanceOfflineMutationRequest,
    organization_id: UUID,
    membership_id: UUID,
    user_id: UUID,
    session_id: UUID,
    permission_keys: set[str],
) -> AttendanceRegister:
    if payload.operation == AttendanceOfflineOperation.CREATE_REGISTER:
        create = payload.create
        if create is None:
            raise WorkforceValidationError("Attendance create payload is required")
        return await create_attendance_register(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=membership_id,
            actor_user_id=user_id,
            attendance_date=create.attendance_date,
            shift_code=create.shift_code,
            notes=create.notes,
            populate_active_workers=create.populate_active_workers,
            session_id=session_id,
        )

    if payload.operation == AttendanceOfflineOperation.REPLACE_ENTRIES:
        entries = payload.entries
        if entries is None:
            raise WorkforceValidationError("Attendance entries payload is required")
        return await replace_attendance_entries(
            db,
            organization_id=organization_id,
            project_id=project_id,
            membership_id=membership_id,
            register_id=payload.entity_id,
            expected_revision=entries.expected_revision,
            entries=[entry.model_dump() for entry in entries.entries],
            actor_user_id=user_id,
            session_id=session_id,
            reason=entries.reason,
        )

    action = payload.action
    if action is None:
        raise WorkforceValidationError("Attendance submit payload is required")
    return await submit_attendance(
        db,
        organization_id=organization_id,
        project_id=project_id,
        membership_id=membership_id,
        register_id=payload.entity_id,
        expected_revision=action.expected_revision,
        actor_user_id=user_id,
        permission_keys=permission_keys,
        session_id=session_id,
        reason=action.reason,
    )


@router.post(
    "/projects/{project_id}/workforce/attendance/offline/mutations",
    response_model=AttendanceOfflineMutationResponse,
    responses={409: {"model": AttendanceOfflineMutationResponse}},
)
async def apply_attendance_offline_mutation(
    project_id: UUID,
    payload: AttendanceOfflineMutationRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> JSONResponse:
    context = await build_access_context(db, session.membership_id)
    permission_keys = _require_project_permission(
        context,
        project_id,
        _permission_for(payload.operation),
    )
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
                register = await _apply_operation(
                    db,
                    project_id=project_id,
                    payload=payload,
                    organization_id=context.organization_id,
                    membership_id=context.membership_id,
                    user_id=session.user_id,
                    session_id=session.id,
                    permission_keys=permission_keys,
                )
        except WorkforceConflictError as exc:
            current = await _current_register(
                db,
                organization_id=context.organization_id,
                project_id=project_id,
                register_id=payload.entity_id,
            )
            if (
                current is not None
                and payload.base_revision is not None
                and current.revision != payload.base_revision
            ):
                server_result = _register_result(current)
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
        except WorkforceValidationError as exc:
            await mark_mutation_rejected(
                db,
                receipt,
                error_code="validation_error",
                result={"detail": str(exc)},
            )
        else:
            receipt.entity_id = str(register.id)
            await mark_mutation_applied(
                db,
                receipt,
                server_version=register.revision,
                result=_register_result(register),
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
