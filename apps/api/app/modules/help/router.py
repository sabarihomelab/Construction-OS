from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.deps import DbSession
from app.modules.audit.models import AuditActorType, AuditRisk
from app.modules.audit.service import record_audit_event
from app.modules.features.service import build_access_context
from app.modules.help.assistant import (
    AssistantProviderError,
    AssistantUnavailableError,
    generate_assistant_answer,
    installation_state_evidence,
    retrieve_product_evidence,
    retrieve_tenant_evidence,
)
from app.modules.help.assistant_schemas import (
    AssistantAnswerRead,
    AssistantCapabilitiesRead,
    AssistantEvidenceRead,
    AssistantQuery,
)
from app.modules.sessions.deps import CsrfProtected, CurrentSession

router = APIRouter(tags=["help"])


def _can_use_upgrade_guidance(permission_keys: set[str], *, enabled: bool) -> bool:
    return enabled and "help.assistant.upgrade" in permission_keys


@router.get("/help/assistant/capabilities", response_model=AssistantCapabilitiesRead)
async def assistant_capabilities(
    db: DbSession,
    session: CurrentSession,
) -> AssistantCapabilitiesRead:
    settings = get_settings()
    context = await build_access_context(db, session.membership_id)
    permissions = set(context.permissions)
    return AssistantCapabilitiesRead(
        enabled=settings.ai_assistant_enabled,
        provider=settings.ai_provider,
        model=settings.ai_model or None,
        allow_tenant_knowledge=settings.ai_allow_tenant_knowledge,
        allow_upgrade_guidance=settings.ai_allow_upgrade_guidance,
        can_use=settings.ai_assistant_enabled and "help.assistant.use" in permissions,
        can_use_upgrade_guidance=_can_use_upgrade_guidance(
            permissions,
            enabled=settings.ai_assistant_enabled and settings.ai_allow_upgrade_guidance,
        ),
    )


@router.post("/help/assistant/query", response_model=AssistantAnswerRead)
async def query_assistant(
    payload: AssistantQuery,
    db: DbSession,
    session: CurrentSession,
    _csrf: CsrfProtected,
) -> AssistantAnswerRead:
    settings = get_settings()
    if not settings.ai_assistant_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Construction OS Assistant is not enabled in this environment",
        )

    context = await build_access_context(db, session.membership_id)
    permissions = set(context.permissions)
    if "help.assistant.use" not in permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if payload.mode.value == "upgrade":
        if not settings.ai_allow_upgrade_guidance:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Upgrade guidance is disabled in this environment",
            )
        if "help.assistant.upgrade" not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    evidence = retrieve_product_evidence(payload.question, mode=payload.mode)
    if payload.mode.value == "upgrade":
        installation = installation_state_evidence()
        if installation is not None:
            evidence.insert(0, installation)

    if payload.include_tenant_knowledge and settings.ai_allow_tenant_knowledge:
        evidence.extend(
            await retrieve_tenant_evidence(
                db,
                organization_id=context.organization_id,
                question=payload.question,
                permission_keys=permissions,
                allowed_scopes={
                    scope_type: set(values) for scope_type, values in context.scopes.items()
                },
            )
        )

    evidence = evidence[:10]
    try:
        answer = await generate_assistant_answer(
            settings,
            question=payload.question,
            mode=payload.mode,
            evidence=evidence,
        )
    except AssistantUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AssistantProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    await record_audit_event(
        db,
        organization_id=context.organization_id,
        action="help.assistant.queried",
        target_type="assistant",
        target_id=payload.mode.value,
        actor_type=AuditActorType.USER,
        actor_user_id=session.user_id,
        session_id=session.id,
        risk=AuditRisk.LOW,
        metadata={
            "mode": payload.mode.value,
            "provider": settings.ai_provider,
            "model": settings.ai_model,
            "evidence_count": len(evidence),
            "tenant_knowledge_requested": payload.include_tenant_knowledge,
        },
    )
    await db.commit()

    return AssistantAnswerRead(
        answer=answer,
        mode=payload.mode,
        provider=settings.ai_provider,
        model=settings.ai_model,
        evidence=[
            AssistantEvidenceRead(
                source_id=item.source_id,
                kind=item.kind,
                title=item.title,
            )
            for item in evidence
        ],
        authoritative=False,
    )
