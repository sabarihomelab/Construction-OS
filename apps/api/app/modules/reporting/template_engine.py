from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_.\[\]-]+)\s*}}")


class TemplateEngineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReportCollectionContract:
    key: str
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportPayloadContract:
    scalar_paths: tuple[str, ...]
    collections: tuple[ReportCollectionContract, ...]

    @property
    def collection_map(self) -> dict[str, ReportCollectionContract]:
        return {item.key: item for item in self.collections}


def _serialize_scalar(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def resolve_path(payload: Mapping[str, object], path: str) -> object | None:
    current: object = payload
    for token in path.split("."):
        if not token:
            return None
        if isinstance(current, Mapping):
            current = current.get(token)
        else:
            return None
    return current


def render_placeholders(text: str | None, payload: Mapping[str, object]) -> str:
    if not text:
        return ""

    def replace(match: re.Match[str]) -> str:
        value = resolve_path(payload, match.group(1))
        if isinstance(value, (Mapping, list, tuple, set)):
            raise TemplateEngineError(
                f"Collection/object placeholder cannot be rendered as scalar text: {match.group(1)}"
            )
        return _serialize_scalar(value)

    return _PLACEHOLDER_RE.sub(replace, text)


def placeholder_paths(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(dict.fromkeys(match.group(1) for match in _PLACEHOLDER_RE.finditer(text)))


def validate_placeholder_text(
    text: str | None,
    *,
    contract: ReportPayloadContract,
) -> None:
    allowed = set(contract.scalar_paths)
    for path in placeholder_paths(text):
        if path not in allowed:
            raise TemplateEngineError(f"Unknown report placeholder: {path}")


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (Sequence, Mapping, set, frozenset)):
        return len(value) == 0
    return False


def evaluate_condition(
    condition: Mapping[str, object] | None,
    payload: Mapping[str, object],
) -> bool:
    if not condition:
        return True
    path = condition.get("path")
    operator = str(condition.get("operator") or "not_empty")
    expected = condition.get("value")
    if not isinstance(path, str) or not path:
        raise TemplateEngineError("Conditional section path is required")
    actual = resolve_path(payload, path)

    if operator == "exists":
        return actual is not None
    if operator == "not_empty":
        return not _is_empty(actual)
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "in":
        return isinstance(expected, (list, tuple, set, frozenset)) and actual in expected
    if operator == "contains":
        return isinstance(actual, (str, list, tuple, set, frozenset)) and expected in actual

    try:
        if operator == "gt":
            return actual is not None and expected is not None and actual > expected  # type: ignore[operator]
        if operator == "gte":
            return actual is not None and expected is not None and actual >= expected  # type: ignore[operator]
        if operator == "lt":
            return actual is not None and expected is not None and actual < expected  # type: ignore[operator]
        if operator == "lte":
            return actual is not None and expected is not None and actual <= expected  # type: ignore[operator]
    except TypeError as exc:
        raise TemplateEngineError(f"Condition values are not comparable for {path}") from exc

    raise TemplateEngineError(f"Unsupported report condition operator: {operator}")


def _table_rows(value: object) -> list[Mapping[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TemplateEngineError("Report collection payload must be a list")
    rows: list[Mapping[str, object]] = []
    for row in value:
        if not isinstance(row, Mapping):
            raise TemplateEngineError("Report collection rows must be objects")
        rows.append(row)
    return rows


def prepare_table_rows(
    rows: list[Mapping[str, object]],
    *,
    table_spec: Mapping[str, object] | None,
) -> list[Mapping[str, object]]:
    if not table_spec:
        return rows
    filtered = rows
    if bool(table_spec.get("hide_empty_rows", True)):
        filtered = [row for row in filtered if any(not _is_empty(value) for value in row.values())]
    sort_by = table_spec.get("sort_by") or []
    if isinstance(sort_by, list):
        for key in reversed([item for item in sort_by if isinstance(item, str)]):
            filtered = sorted(
                filtered,
                key=lambda row: (row.get(key) is None, _serialize_scalar(row.get(key)).lower()),
            )
    return filtered


def validate_layout_contract(
    layout: Mapping[str, object],
    *,
    contract: ReportPayloadContract,
    element_collections: Mapping[str, str | None],
) -> None:
    branding = layout.get("branding")
    header_footer = layout.get("header_footer")
    if isinstance(branding, Mapping):
        validate_placeholder_text(branding.get("report_title"), contract=contract)  # type: ignore[arg-type]
    if isinstance(header_footer, Mapping):
        for key in (
            "header_left",
            "header_center",
            "header_right",
            "footer_left",
            "footer_center",
            "footer_right",
        ):
            validate_placeholder_text(header_footer.get(key), contract=contract)  # type: ignore[arg-type]

    elements = layout.get("elements")
    if not isinstance(elements, list):
        raise TemplateEngineError("Report layout elements must be a list")
    collection_map = contract.collection_map
    for element in elements:
        if not isinstance(element, Mapping):
            raise TemplateEngineError("Report layout element must be an object")
        validate_placeholder_text(element.get("title"), contract=contract)  # type: ignore[arg-type]
        validate_placeholder_text(element.get("custom_text"), contract=contract)  # type: ignore[arg-type]
        kind = str(element.get("kind") or "")
        collection_key = element_collections.get(kind)
        if collection_key is None:
            continue
        collection = collection_map.get(collection_key)
        if collection is None:
            raise TemplateEngineError(f"Layout references unknown collection: {collection_key}")
        table = element.get("table")
        if not isinstance(table, Mapping):
            continue
        columns = table.get("columns") or []
        if not isinstance(columns, list):
            raise TemplateEngineError("Report table columns must be a list")
        allowed_fields = set(collection.fields)
        for column in columns:
            if not isinstance(column, Mapping):
                raise TemplateEngineError("Report table column must be an object")
            key = column.get("key")
            if not isinstance(key, str) or key not in allowed_fields:
                raise TemplateEngineError(
                    f"Unknown column {key!r} for report collection {collection_key}"
                )


def visible_layout_elements(
    layout: Mapping[str, object],
    payload: Mapping[str, object],
) -> list[Mapping[str, object]]:
    elements = layout.get("elements")
    if not isinstance(elements, list):
        return []
    visible: list[Mapping[str, object]] = []
    for raw in elements:
        if not isinstance(raw, Mapping) or not bool(raw.get("visible", True)):
            continue
        condition = raw.get("condition")
        if condition is not None and not isinstance(condition, Mapping):
            raise TemplateEngineError("Report element condition must be an object")
        if not evaluate_condition(condition, payload):
            continue
        visible.append(raw)
    return sorted(visible, key=lambda item: int(item.get("order") or 0))


def collection_rows(
    payload: Mapping[str, object],
    collection_key: str,
    table_spec: Mapping[str, object] | None,
) -> list[Mapping[str, object]]:
    return prepare_table_rows(
        _table_rows(resolve_path(payload, collection_key)),
        table_spec=table_spec,
    )


def render_generic_html(
    *,
    payload: Mapping[str, object],
    layout: Mapping[str, object],
    element_collections: Mapping[str, str | None],
) -> str:
    page = layout.get("page") if isinstance(layout.get("page"), Mapping) else {}
    orientation = str(page.get("orientation") or "portrait")
    size = str(page.get("size") or "a4").upper()
    margins = " ".join(
        f"{int(page.get(key) or 12)}mm"
        for key in ("margin_top_mm", "margin_right_mm", "margin_bottom_mm", "margin_left_mm")
    )
    branding = layout.get("branding") if isinstance(layout.get("branding"), Mapping) else {}
    title = render_placeholders(str(branding.get("report_title") or "Report"), payload)
    pieces = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title>",
        "<style>",
        f"@page {{ size: {size} {orientation}; margin: {margins}; }}",
        "body{font-family:Arial,sans-serif;color:#222;font-size:10pt}",
        ".grid{display:flex;flex-wrap:wrap;gap:0}.block{box-sizing:border-box;padding:5px}",
        "h1{font-size:18pt;margin:0 0 8px}h2{font-size:12pt;margin:8px 0 4px}",
        "table{width:100%;border-collapse:collapse;margin-bottom:8px}",
        "th,td{border:1px solid #bbb;padding:4px;vertical-align:top}",
        "thead{display:table-header-group}tr{break-inside:avoid}",
        ".page-break{break-before:page}.muted{color:#666}",
        "</style></head><body>",
        f"<h1>{html.escape(title)}</h1><div class='grid'>",
    ]
    for element in visible_layout_elements(layout, payload):
        kind = str(element.get("kind") or "")
        if kind == "page_break":
            pieces.append("</div><div class='page-break'></div><div class='grid'>")
            continue
        width = int(element.get("width_percent") or 100)
        css = f"width:{width}%"
        if bool(element.get("page_break_before", False)):
            pieces.append("</div><div class='page-break'></div><div class='grid'>")
        title_text = render_placeholders(str(element.get("title") or ""), payload)
        collection_key = element_collections.get(kind)
        pieces.append(f"<section class='block' style='{css}'>")
        if title_text:
            pieces.append(f"<h2>{html.escape(title_text)}</h2>")
        if kind == "custom_text":
            rendered = render_placeholders(str(element.get("custom_text") or ""), payload)
            pieces.append(f"<div>{html.escape(rendered).replace(chr(10), '<br>')}</div>")
        elif collection_key:
            table_spec = element.get("table") if isinstance(element.get("table"), Mapping) else {}
            rows = collection_rows(payload, collection_key, table_spec)
            hide_when_empty = bool(element.get("hide_when_empty", True))
            if rows or not hide_when_empty:
                columns_raw = table_spec.get("columns") if isinstance(table_spec, Mapping) else []
                columns = [item for item in columns_raw if isinstance(item, Mapping) and bool(item.get("visible", True))]
                columns = sorted(columns, key=lambda item: int(item.get("order") or 0))
                if not columns and rows:
                    columns = [{"key": key, "label": key.replace("_", " ").title()} for key in rows[0].keys()]
                pieces.append("<table><thead><tr>")
                for column in columns:
                    pieces.append(f"<th>{html.escape(str(column.get('label') or column.get('key') or ''))}</th>")
                pieces.append("</tr></thead><tbody>")
                for row in rows:
                    pieces.append("<tr>")
                    for column in columns:
                        value = row.get(str(column.get("key")))
                        pieces.append(f"<td>{html.escape(_serialize_scalar(value))}</td>")
                    pieces.append("</tr>")
                pieces.append("</tbody></table>")
        else:
            value = resolve_path(payload, kind)
            if isinstance(value, Mapping):
                pieces.append("<table><tbody>")
                for key, item in value.items():
                    if _is_empty(item):
                        continue
                    pieces.append(
                        f"<tr><th>{html.escape(str(key).replace('_', ' ').title())}</th>"
                        f"<td>{html.escape(_serialize_scalar(item))}</td></tr>"
                    )
                pieces.append("</tbody></table>")
            elif value is not None:
                pieces.append(f"<div>{html.escape(_serialize_scalar(value))}</div>")
        pieces.append("</section>")
    pieces.append("</div></body></html>")
    return "".join(pieces)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
