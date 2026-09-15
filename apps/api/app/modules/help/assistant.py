import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.help.service import visible_knowledge_chunks


class AssistantMode(StrEnum):
    HELP = "help"
    CONFIGURATION = "configuration"
    UPGRADE = "upgrade"


class AssistantUnavailableError(RuntimeError):
    pass


class AssistantProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProductKnowledgeDocument:
    key: str
    title: str
    relative_path: str
    modes: tuple[AssistantMode, ...]


@dataclass(frozen=True, slots=True)
class AssistantEvidence:
    source_id: str
    kind: str
    title: str
    content: str


PRODUCT_KNOWLEDGE_DOCUMENTS: tuple[ProductKnowledgeDocument, ...] = (
    ProductKnowledgeDocument(
        key="india-product-contract",
        title="India-First Product Contract",
        relative_path="docs/product/INDIA-FIRST-PRODUCT-CONTRACT.md",
        modes=(AssistantMode.HELP, AssistantMode.CONFIGURATION, AssistantMode.UPGRADE),
    ),
    ProductKnowledgeDocument(
        key="india-release-baseline",
        title="India Demo Build Release Baseline",
        relative_path="docs/product/RELEASE-REQUIREMENTS-BASELINE.md",
        modes=(AssistantMode.HELP, AssistantMode.CONFIGURATION, AssistantMode.UPGRADE),
    ),
    ProductKnowledgeDocument(
        key="installation-lifecycle",
        title="Installation Lifecycle",
        relative_path="docs/operations/INSTALLATION-LIFECYCLE.md",
        modes=(AssistantMode.HELP, AssistantMode.UPGRADE),
    ),
    ProductKnowledgeDocument(
        key="deployment-composition",
        title="Deployment Composition",
        relative_path="docs/architecture/DEPLOYMENT-COMPOSITION.md",
        modes=(AssistantMode.HELP, AssistantMode.CONFIGURATION, AssistantMode.UPGRADE),
    ),
    ProductKnowledgeDocument(
        key="module-contract",
        title="Module Contract",
        relative_path="docs/product/MODULE-CONTRACT.md",
        modes=(AssistantMode.HELP, AssistantMode.CONFIGURATION),
    ),
    ProductKnowledgeDocument(
        key="assistant-rag",
        title="Construction OS Assistant RAG Architecture",
        relative_path="docs/architecture/IN_APP_ASSISTANT_RAG.md",
        modes=(AssistantMode.HELP, AssistantMode.UPGRADE),
    ),
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{2,}")
_STOPWORDS = {
    "and",
    "are",
    "can",
    "for",
    "from",
    "how",
    "into",
    "our",
    "the",
    "this",
    "that",
    "what",
    "when",
    "where",
    "which",
    "with",
    "you",
    "your",
}


def _repository_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "VERSION").is_file() and (parent / "docs").is_dir():
            return parent
    return None


def _query_terms(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.lower())
        if token not in _STOPWORDS
    }


def _split_document(content: str, *, max_chars: int = 2400) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars])
            continue
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _score_content(terms: set[str], content: str) -> int:
    if not terms:
        return 1
    lowered = content.lower()
    return sum(min(lowered.count(term), 8) for term in terms)


def retrieve_product_evidence(
    question: str,
    *,
    mode: AssistantMode,
    max_items: int = 6,
) -> list[AssistantEvidence]:
    root = _repository_root()
    if root is None:
        return []
    terms = _query_terms(question)
    ranked: list[tuple[int, AssistantEvidence]] = []
    for document in PRODUCT_KNOWLEDGE_DOCUMENTS:
        if mode not in document.modes:
            continue
        path = root / document.relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for ordinal, chunk in enumerate(_split_document(content)):
            score = _score_content(terms, chunk)
            if score <= 0:
                continue
            ranked.append(
                (
                    score,
                    AssistantEvidence(
                        source_id=f"product:{document.key}:{ordinal}",
                        kind="product",
                        title=document.title,
                        content=chunk,
                    ),
                )
            )
    ranked.sort(key=lambda item: (-item[0], item[1].source_id))
    return [item[1] for item in ranked[:max_items]]


def installation_state_evidence() -> AssistantEvidence | None:
    root = _repository_root()
    if root is None:
        return None
    state_path = root / ".construction-os" / "install-state.json"
    version_path = root / "VERSION"
    safe: dict[str, object] = {}
    if version_path.is_file():
        safe["release_version_on_disk"] = version_path.read_text(encoding="utf-8").strip()
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}
        for key in (
            "release_version",
            "environment",
            "environment_name",
            "deployment_profile",
            "database_mode",
            "database_endpoint",
            "storage_provider",
            "runtime_modules",
            "worker_profiles",
            "last_migration",
            "last_backup",
        ):
            if key in state:
                safe[key] = state[key]
    if not safe:
        return None
    return AssistantEvidence(
        source_id="installation:current",
        kind="installation",
        title="Current Installation State",
        content=json.dumps(safe, indent=2, sort_keys=True),
    )


async def retrieve_tenant_evidence(
    db: AsyncSession,
    *,
    organization_id: UUID,
    question: str,
    permission_keys: set[str],
    allowed_scopes: dict[str, set[str]],
    max_items: int = 4,
) -> list[AssistantEvidence]:
    terms = _query_terms(question)
    chunks = await visible_knowledge_chunks(
        db,
        organization_id=organization_id,
        permission_keys=permission_keys,
        allowed_scopes=allowed_scopes,
        limit=200,
    )
    ranked: list[tuple[int, AssistantEvidence]] = []
    for chunk in chunks:
        score = _score_content(terms, chunk.content)
        if score <= 0:
            continue
        title = chunk.heading or f"Company knowledge {chunk.source_id}"
        ranked.append(
            (
                score,
                AssistantEvidence(
                    source_id=f"tenant:{chunk.source_id}:{chunk.source_version}:{chunk.ordinal}",
                    kind="tenant",
                    title=title,
                    content=chunk.content[:4000],
                ),
            )
        )
    ranked.sort(key=lambda item: (-item[0], item[1].source_id))
    return [item[1] for item in ranked[:max_items]]


def build_prompt(question: str, mode: AssistantMode, evidence: list[AssistantEvidence]) -> list[dict[str, str]]:
    system = (
        "You are Construction OS Assistant for an India-first construction operating platform. "
        "Answer factual product, installation and company-knowledge questions only from the evidence supplied. "
        "Cite evidence identifiers in square brackets such as [product:...]. "
        "If evidence is insufficient, say that you cannot determine the answer from available Construction OS evidence. "
        "Never claim that you executed an upgrade, migration, rollback, configuration change, approval or business transaction. "
        "Never invent current GST, TDS, withholding, e-invoice or other statutory rates/thresholds. "
        "Measurement, certification, RA billing, tax, payment, budget and approval outcomes remain authoritative domain/human decisions. "
        "Keep guidance practical and concise."
    )
    evidence_text = "\n\n".join(
        f"[{item.source_id}] {item.title}\n{item.content}" for item in evidence
    )
    user = f"Mode: {mode.value}\n\nQuestion:\n{question}\n\nEvidence:\n{evidence_text}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user[:30000]},
    ]


async def generate_assistant_answer(
    settings: Settings,
    *,
    question: str,
    mode: AssistantMode,
    evidence: list[AssistantEvidence],
) -> str:
    if not settings.ai_assistant_enabled or settings.ai_provider == "disabled":
        raise AssistantUnavailableError("Construction OS Assistant is not configured in this environment")
    if not evidence:
        return "I cannot determine that from the Construction OS evidence currently available to me."

    messages = build_prompt(question, mode, evidence)
    timeout = httpx.Timeout(45.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if settings.ai_provider == "ollama":
            response = await client.post(
                f"{settings.ai_base_url.rstrip('/')}/api/chat",
                json={"model": settings.ai_model, "messages": messages, "stream": False},
            )
            try:
                response.raise_for_status()
                content = response.json()["message"]["content"]
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                raise AssistantProviderError("Local assistant provider returned an invalid response") from exc
        elif settings.ai_provider == "openai_compatible":
            headers = {"Content-Type": "application/json"}
            if settings.ai_api_key:
                headers["Authorization"] = f"Bearer {settings.ai_api_key}"
            response = await client.post(
                f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={"model": settings.ai_model, "messages": messages, "temperature": 0.1},
            )
            try:
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPError, IndexError, KeyError, TypeError, ValueError) as exc:
                raise AssistantProviderError("Assistant provider returned an invalid response") from exc
        else:
            raise AssistantUnavailableError("Unsupported assistant provider")

    if not isinstance(content, str) or not content.strip():
        raise AssistantProviderError("Assistant provider returned an empty response")
    return content.strip()
