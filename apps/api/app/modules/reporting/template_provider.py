import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reporting.template_schemas import (
    DisplayCondition,
    ReportBlock,
    ReportBlockKind,
    ReportLayoutSpec,
)

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")


class ReportTemplateValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CollectionContract:
    key: str
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportDataContract:
    key: str
    version: int
    scalar_paths: tuple[str, ...]
    collections: tuple[CollectionContract, ...]
    source_revision_path: str = "report.revision"
    dynamic_prefixes: tuple[str, ...] = ()
    required_permission_key: str | None = None

    def collection_map(self) -> dict[str, CollectionContract]:
        return {item.key: item for item in self.collections}

    def path_allowed(self, path: str) -> bool:
        if path in self.scalar_paths:
            return True
        if path in self.collection_map():
            return True
        return any(path.startswith(prefix) for prefix in self.dynamic_prefixes)


PayloadBuilder = Callable[
    [AsyncSession, UUID, UUID | None, UUID],
    Awaitable[dict[str, object]],
]
DefaultLayoutFactory = Callable[[], ReportLayoutSpec]


@dataclass(frozen=True, slots=True)
class ReportDataProvider:
    contract: ReportDataContract
    source_entity_type: str
    build_payload: PayloadBuilder
    default_layout: DefaultLayoutFactory | None = None


class ReportDataProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ReportDataProvider] = {}

    def register(self, provider: ReportDataProvider) -> None:
        key = provider.contract.key.strip()
        if not key:
            raise ValueError("Report provider key is required")
        if key in self._providers:
            raise ValueError(f"Report provider already registered: {key}")
        if provider.contract.version < 1:
            raise ValueError("Report provider contract version must be positive")
        if not provider.contract.source_revision_path.strip():
            raise ValueError("Report provider source_revision_path is required")
        self._providers[key] = provider

    def get(self, key: str) -> ReportDataProvider:
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ReportTemplateValidationError(f"Unknown report data provider: {key}") from exc

    def contains(self, key: str) -> bool:
        return key in self._providers


report_data_providers = ReportDataProviderRegistry()


def placeholders_in_text(value: str | None) -> set[str]:
    if not value:
        return set()
    return set(_PLACEHOLDER_PATTERN.findall(value))


def _validate_condition(condition: DisplayCondition | None, contract: ReportDataContract) -> None:
    if condition is None:
        return
    if not contract.path_allowed(condition.path):
        raise ReportTemplateValidationError(
            f"Display condition references an unknown provider path: {condition.path}"
        )


def _validate_placeholders(text: str | None, contract: ReportDataContract) -> None:
    for placeholder in placeholders_in_text(text):
        if not contract.path_allowed(placeholder):
            raise ReportTemplateValidationError(
                f"Template placeholder is not provided by {contract.key}: {placeholder}"
            )


def _validate_block(block: ReportBlock, contract: ReportDataContract) -> None:
    _validate_placeholders(block.title, contract)
    _validate_placeholders(block.text_template, contract)
    _validate_condition(block.condition, contract)
    if block.kind == ReportBlockKind.FIELD_GROUP:
        for path in block.scalar_fields:
            if not contract.path_allowed(path):
                raise ReportTemplateValidationError(
                    f"Field group references an unknown provider path: {path}"
                )
    if block.kind == ReportBlockKind.IMAGE:
        if block.image_placeholder is None or not contract.path_allowed(block.image_placeholder):
            raise ReportTemplateValidationError(
                f"Image block references an unknown provider path: {block.image_placeholder}"
            )
    if block.kind == ReportBlockKind.TABLE:
        collections = contract.collection_map()
        if block.data_key not in collections:
            raise ReportTemplateValidationError(
                f"Table references an unknown provider collection: {block.data_key}"
            )
        allowed_fields = set(collections[block.data_key].fields)
        for column in block.table_columns:
            if column.key not in allowed_fields:
                raise ReportTemplateValidationError(
                    f"Table column {column.key} is not available in {block.data_key}"
                )
        for rule in block.sort_by:
            if rule.key not in allowed_fields:
                raise ReportTemplateValidationError(
                    f"Table sort field {rule.key} is not available in {block.data_key}"
                )
        for key in block.group_by:
            if key not in allowed_fields:
                raise ReportTemplateValidationError(
                    f"Table group field {key} is not available in {block.data_key}"
                )


def validate_layout_against_contract(
    layout: ReportLayoutSpec,
    contract: ReportDataContract,
) -> None:
    _validate_placeholders(layout.report_title, contract)
    header_footer = layout.header_footer
    for value in (
        header_footer.header_left,
        header_footer.header_center,
        header_footer.header_right,
        header_footer.footer_left,
        header_footer.footer_center,
        header_footer.footer_right,
    ):
        _validate_placeholders(value, contract)
    for block in layout.blocks:
        _validate_block(block, contract)


def resolve_path(payload: Mapping[str, object], path: str) -> object | None:
    current: object = payload
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current
