from pydantic import BaseModel, Field

from app.modules.help.assistant import AssistantMode


class AssistantCapabilitiesRead(BaseModel):
    enabled: bool
    provider: str
    model: str | None
    allow_tenant_knowledge: bool
    allow_upgrade_guidance: bool
    can_use: bool
    can_use_upgrade_guidance: bool


class AssistantQuery(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    mode: AssistantMode = AssistantMode.HELP
    include_tenant_knowledge: bool = True


class AssistantEvidenceRead(BaseModel):
    source_id: str
    kind: str
    title: str


class AssistantAnswerRead(BaseModel):
    answer: str
    mode: AssistantMode
    provider: str
    model: str
    evidence: list[AssistantEvidenceRead]
    authoritative: bool = False
