from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DrawingRenderRequest:
    organization_id: str
    drawing_revision_id: str
    source_provider_key: str
    source_storage_key: str
    source_page: int
    render_version: int


@dataclass(frozen=True, slots=True)
class DrawingRenderResult:
    renderer_key: str
    page_width: Decimal
    page_height: Decimal
    manifest: dict[str, object]
    geometry_metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class DrawingComparisonRequest:
    organization_id: str
    comparison_id: str
    base_manifest: dict[str, object]
    compare_manifest: dict[str, object]


@dataclass(frozen=True, slots=True)
class DrawingComparisonResult:
    alignment: dict[str, object]
    result_manifest: dict[str, object]


class DrawingRenderer(Protocol):
    @property
    def renderer_key(self) -> str: ...

    async def render(self, request: DrawingRenderRequest) -> DrawingRenderResult: ...

    async def compare(self, request: DrawingComparisonRequest) -> DrawingComparisonResult: ...


class DrawingRendererRegistry:
    def __init__(self) -> None:
        self._renderers: dict[str, DrawingRenderer] = {}

    def register(self, renderer: DrawingRenderer) -> None:
        key = renderer.renderer_key.strip()
        if not key:
            raise ValueError("Drawing renderer key is required")
        if key in self._renderers:
            raise ValueError(f"Drawing renderer is already registered: {key}")
        self._renderers[key] = renderer

    def get(self, renderer_key: str) -> DrawingRenderer:
        try:
            return self._renderers[renderer_key]
        except KeyError as exc:
            raise KeyError(f"Unknown drawing renderer: {renderer_key}") from exc

    def default(self) -> DrawingRenderer:
        if not self._renderers:
            raise RuntimeError("No drawing renderer has been configured")
        return self._renderers[min(self._renderers)]


drawing_renderers = DrawingRendererRegistry()
