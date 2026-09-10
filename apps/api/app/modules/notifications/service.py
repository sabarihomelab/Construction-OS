from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.service import enqueue_event, sanitize_event_payload
from app.modules.identity.models import MembershipStatus, OrganizationMembership, UserPreference
from app.modules.jobs.service import enqueue_job
from app.modules.notifications.digests import (
    NotificationDigest,
    NotificationDigestItem,
    NotificationDigestStatus,
)
from app.modules.notifications.models import (
    DigestFrequency,
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryMode,
    NotificationDeliveryStatus,
    NotificationPreference,
    NotificationSettings,
)
from app.modules.organizations.models import OrganizationSettings


class NotificationValidationError(ValueError):
    pass


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise NotificationValidationError(f"Unknown IANA timezone: {timezone_name}") from exc


def _local_datetime(day: date, local_time: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, local_time, tzinfo=zone)


def next_allowed_delivery_time(
    now: datetime,
    *,
    timezone_name: str,
    quiet_hours_enabled: bool,
    quiet_start: time | None,
    quiet_end: time | None,
) -> datetime:
    if now.tzinfo is None:
        raise NotificationValidationError("Delivery time must be timezone-aware")
    if not quiet_hours_enabled:
        return now.astimezone(UTC)
    if quiet_start is None or quiet_end is None or quiet_start == quiet_end:
        raise NotificationValidationError("Valid quiet-hour start/end values are required")

    zone = _zone(timezone_name)
    local_now = now.astimezone(zone)
    current_time = local_now.timetz().replace(tzinfo=None)

    if quiet_start < quiet_end:
        in_quiet = quiet_start <= current_time < quiet_end
        quiet_end_day = local_now.date()
    else:
        in_quiet = current_time >= quiet_start or current_time < quiet_end
        quiet_end_day = (
            local_now.date() + timedelta(days=1)
            if current_time >= quiet_start
            else local_now.date()
        )

    if not in_quiet:
        return now.astimezone(UTC)
    return _local_datetime(quiet_end_day, quiet_end, zone).astimezone(UTC)


def next_digest_window(
    now: datetime,
    *,
    timezone_name: str,
    frequency: DigestFrequency,
    digest_time: time,
) -> tuple[datetime, datetime]:
    if now.tzinfo is None:
        raise NotificationValidationError("Digest time must be timezone-aware")
    zone = _zone(timezone_name)
    local_now = now.astimezone(zone)

    if frequency == DigestFrequency.HOURLY:
        start = local_now.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
    elif frequency == DigestFrequency.DAILY:
        today_at_digest = _local_datetime(local_now.date(), digest_time, zone)
        if local_now < today_at_digest:
            end = today_at_digest
            start = _local_datetime(local_now.date() - timedelta(days=1), digest_time, zone)
        else:
            start = today_at_digest
            end = _local_datetime(local_now.date() + timedelta(days=1), digest_time, zone)
    else:
        week_start = local_now.date() - timedelta(days=local_now.weekday())
        this_week = _local_datetime(week_start, digest_time, zone)
        if local_now < this_week:
            end = this_week
            start = _local_datetime(week_start - timedelta(days=7), digest_time, zone)
        else:
            start = this_week
            end = _local_datetime(week_start + timedelta(days=7), digest_time, zone)

    return start.astimezone(UTC), end.astimezone(UTC)


async def _delivery_timezone(
    db: AsyncSession,
    membership: OrganizationMembership,
) -> str:
    notification_settings = await db.get(NotificationSettings, membership.id)
    if notification_settings is not None and notification_settings.timezone:
        return notification_settings.timezone
    user_preference = await db.get(UserPreference, membership.user_id)
    if user_preference is not None and user_preference.timezone:
        return user_preference.timezone
    organization_settings = await db.get(OrganizationSettings, membership.organization_id)
    if organization_settings is not None:
        return organization_settings.timezone
    return "UTC"


async def create_notification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    recipient_membership_id: UUID,
    event_type: str,
    category: NotificationCategory,
    reason_code: str,
    reason_text: str,
    title: str,
    message: str,
    required_permission_key: str | None = None,
    scope_type: str | None = None,
    scope_id: str | UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | UUID | None = None,
    dedupe_key: str | None = None,
    template_key: str | None = None,
    template_variables: dict[str, object] | None = None,
    created_by_user_id: UUID | None = None,
    correlation_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> Notification:
    if not event_type.strip() or not reason_code.strip() or not reason_text.strip():
        raise NotificationValidationError("Event type and notification reason are required")
    if not title.strip() or not message.strip():
        raise NotificationValidationError("Notification title and message are required")
    if (scope_type is None) != (scope_id is None):
        raise NotificationValidationError("scope_type and scope_id must be supplied together")

    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == recipient_membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise NotificationValidationError("Active recipient membership was not found")

    normalized_dedupe = dedupe_key.strip() if dedupe_key else None
    if normalized_dedupe:
        existing = await db.scalar(
            select(Notification).where(
                Notification.organization_id == organization_id,
                Notification.recipient_membership_id == recipient_membership_id,
                Notification.dedupe_key == normalized_dedupe,
            )
        )
        if existing is not None:
            return existing

    notification = Notification(
        organization_id=organization_id,
        recipient_membership_id=recipient_membership_id,
        event_type=event_type.strip(),
        category=category,
        reason_code=reason_code.strip(),
        reason_text=reason_text.strip()[:500],
        title=title.strip()[:255],
        message=message.strip()[:4000],
        template_key=template_key.strip() if template_key else None,
        template_variables=sanitize_event_payload(template_variables),
        required_permission_key=required_permission_key,
        scope_type=scope_type,
        scope_id=str(scope_id) if scope_id is not None else None,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        dedupe_key=normalized_dedupe,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
    )
    db.add(notification)
    await db.flush()

    await enqueue_event(
        db,
        organization_id=organization_id,
        recipient_membership_id=recipient_membership_id,
        event_type="notification.created",
        entity_type="notification",
        entity_id=notification.id,
        required_permission_key=required_permission_key,
        scope_type=scope_type,
        scope_id=scope_id,
        actor_user_id=created_by_user_id,
        correlation_id=correlation_id,
        payload={"notification_id": notification.id, "category": category.value},
    )
    return notification


async def _preference_for(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    event_type: str,
    channel: NotificationChannel,
) -> NotificationPreference | None:
    exact = await db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.organization_id == organization_id,
            NotificationPreference.membership_id == membership_id,
            NotificationPreference.event_type == event_type,
            NotificationPreference.channel == channel,
        )
    )
    if exact is not None:
        return exact
    return await db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.organization_id == organization_id,
            NotificationPreference.membership_id == membership_id,
            NotificationPreference.event_type == "*",
            NotificationPreference.channel == channel,
        )
    )


async def schedule_delivery(
    db: AsyncSession,
    *,
    notification: Notification,
    membership: OrganizationMembership,
    channel: NotificationChannel,
    now: datetime | None = None,
    respect_quiet_hours: bool = True,
) -> NotificationDelivery | NotificationDigest | None:
    if notification.organization_id != membership.organization_id:
        raise NotificationValidationError("Notification and membership tenant do not match")
    if notification.recipient_membership_id != membership.id:
        raise NotificationValidationError("Notification recipient does not match membership")
    if channel == NotificationChannel.IN_APP:
        return None

    preference = await _preference_for(
        db,
        organization_id=notification.organization_id,
        membership_id=membership.id,
        event_type=notification.event_type,
        channel=channel,
    )
    if preference is not None and (
        not preference.enabled or preference.delivery_mode == NotificationDeliveryMode.OFF
    ):
        delivery = NotificationDelivery(
            organization_id=notification.organization_id,
            notification_id=notification.id,
            channel=channel,
            status=NotificationDeliveryStatus.SKIPPED,
            scheduled_at=now or datetime.now(UTC),
            last_error_code="disabled_by_preference",
        )
        db.add(delivery)
        await db.flush()
        return delivery

    current = now or datetime.now(UTC)
    settings = await db.get(NotificationSettings, membership.id)
    timezone_name = await _delivery_timezone(db, membership)
    delivery_mode = (
        preference.delivery_mode if preference is not None else NotificationDeliveryMode.IMMEDIATE
    )

    if delivery_mode == NotificationDeliveryMode.DIGEST:
        frequency = (
            preference.digest_frequency
            if preference is not None and preference.digest_frequency is not None
            else DigestFrequency.DAILY
        )
        digest_time = settings.digest_time if settings is not None and settings.digest_time else time(8, 0)
        window_start, window_end = next_digest_window(
            current,
            timezone_name=timezone_name,
            frequency=frequency,
            digest_time=digest_time,
        )
        digest = await db.scalar(
            select(NotificationDigest).where(
                NotificationDigest.organization_id == notification.organization_id,
                NotificationDigest.membership_id == membership.id,
                NotificationDigest.channel == channel,
                NotificationDigest.frequency == frequency,
                NotificationDigest.window_start == window_start,
                NotificationDigest.window_end == window_end,
            )
        )
        if digest is None:
            digest = NotificationDigest(
                organization_id=notification.organization_id,
                membership_id=membership.id,
                channel=channel,
                frequency=frequency,
                status=NotificationDigestStatus.QUEUED,
                window_start=window_start,
                window_end=window_end,
                scheduled_at=window_end,
                item_count=0,
            )
            db.add(digest)
            await db.flush()

        existing_item = await db.scalar(
            select(NotificationDigestItem).where(
                NotificationDigestItem.digest_id == digest.id,
                NotificationDigestItem.notification_id == notification.id,
            )
        )
        if existing_item is None:
            db.add(
                NotificationDigestItem(
                    digest_id=digest.id,
                    notification_id=notification.id,
                    organization_id=notification.organization_id,
                )
            )
            digest.item_count += 1
            await db.flush()

        await enqueue_job(
            db,
            organization_id=notification.organization_id,
            job_type="notifications.send_digest",
            idempotency_key=f"notification-digest:{digest.id}:send:v1",
            payload={"digest_id": digest.id},
            available_at=digest.scheduled_at,
        )
        return digest

    scheduled_at = current
    if respect_quiet_hours and settings is not None and settings.quiet_hours_enabled:
        scheduled_at = next_allowed_delivery_time(
            current,
            timezone_name=timezone_name,
            quiet_hours_enabled=True,
            quiet_start=settings.quiet_start,
            quiet_end=settings.quiet_end,
        )

    existing = await db.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.notification_id == notification.id,
            NotificationDelivery.channel == channel,
        )
    )
    if existing is not None:
        return existing

    delivery = NotificationDelivery(
        organization_id=notification.organization_id,
        notification_id=notification.id,
        channel=channel,
        status=NotificationDeliveryStatus.QUEUED,
        scheduled_at=scheduled_at,
    )
    db.add(delivery)
    await db.flush()
    await enqueue_job(
        db,
        organization_id=notification.organization_id,
        job_type="notifications.deliver",
        idempotency_key=f"notification-delivery:{delivery.id}:send:v1",
        payload={"notification_delivery_id": delivery.id},
        available_at=scheduled_at,
    )
    return delivery


async def mark_notification_read(
    db: AsyncSession,
    *,
    notification_id: UUID,
    organization_id: UUID,
    membership_id: UUID,
    now: datetime | None = None,
) -> Notification:
    notification = await db.scalar(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.organization_id == organization_id,
            Notification.recipient_membership_id == membership_id,
        )
        .with_for_update()
    )
    if notification is None:
        raise NotificationValidationError("Notification was not found")
    notification.read_at = notification.read_at or (now or datetime.now(UTC))
    await db.flush()
    return notification
