from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DbSession
from app.modules.identity.models import OrganizationMembership
from app.modules.offline.models import ClientDevice, DeviceSyncState
from app.modules.offline.schemas import (
    ClientDeviceRead,
    DeviceRegistrationRequest,
    DeviceSyncStateRead,
    EventAcknowledgementRequest,
)
from app.modules.offline.service import acknowledge_event_sequence, register_device
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(prefix="/offline", tags=["offline"])


async def _current_membership(db: DbSession, session: CurrentSession) -> OrganizationMembership:
    membership = await db.get(OrganizationMembership, session.membership_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Active organization membership is required",
        )
    return membership


async def _owned_device(
    db: DbSession,
    session: CurrentSession,
    device_id: UUID,
) -> ClientDevice:
    membership = await _current_membership(db, session)
    device = await db.get(ClientDevice, device_id)
    if (
        device is None
        or device.organization_id != membership.organization_id
        or device.user_id != session.user_id
        or device.revoked_at is not None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device was not found")
    return device


@router.post("/devices", response_model=ClientDeviceRead)
async def create_or_refresh_device(
    request: DeviceRegistrationRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> ClientDevice:
    membership = await _current_membership(db, session)
    device = await register_device(
        db,
        organization_id=membership.organization_id,
        user_id=session.user_id,
        installation_id=request.installation_id,
        platform=request.platform,
        device_label=request.device_label,
        app_version=request.app_version,
    )
    await db.commit()
    return device


@router.get("/devices/{device_id}/state", response_model=DeviceSyncStateRead)
async def get_device_sync_state(
    device_id: UUID,
    db: DbSession,
    session: CurrentSession,
) -> DeviceSyncState:
    device = await _owned_device(db, session, device_id)
    state = await db.get(DeviceSyncState, device.id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync state was not found")
    return state


@router.post("/events/ack", response_model=DeviceSyncStateRead)
async def acknowledge_realtime_events(
    request: EventAcknowledgementRequest,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> DeviceSyncState:
    device = await _owned_device(db, session, request.device_id)
    state = await acknowledge_event_sequence(
        db,
        organization_id=device.organization_id,
        device_id=device.id,
        sequence=request.sequence,
    )
    await db.commit()
    return state
