"""Deterministic active-Todo Markdown projection.

The user/agent Todo sections are machine-owned after authority promotion.
Everything outside those sections remains opaque human-authored Markdown and
is preserved byte-for-byte. Canonical provider records remain the truth; the
readable Markdown syntax is regenerated and then parsed back for parity.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..coordination.coordination_state_contract import (
    TODO_CANONICAL_READ_RECORD_FIELDS,
    TODO_CANONICAL_REQUIRED_READ_FIELDS,
    TODO_DOMAIN_ITEM_SCHEMA_VERSION,
    TODO_DOMAIN_RECORD_FIELDS,
    TODO_DOMAIN_REQUIRED_FIELDS,
    TODO_ITEM_SCHEMA_VERSION,
    canonical_record_fields,
)
from .active_state_editing import (
    COMPLETED_WORK_ARCHIVE_HEADING,
    TODO_SECTION_HEADINGS,
    archive_section_bounds,
    todo_blocks,
)
from .machine_region import find_todo_regions, todo_region_marker
from .completion_validation_projection import (
    completion_validation_declaration,
    completion_validation_declaration_sha256,
    project_completion_validation_authority,
)
from .active_state_todo_parser import parse_active_state_todos
from .contract import (
    TODO_METADATA_FIELDS,
    TODO_STATUS_OPEN,
    format_todo_metadata_line,
    normalize_todo_status,
    require_todo_decision_scope,
    todo_marker_for_status,
)
from .todo_summary import canonical_todo_read_record


TODO_SECTION_PROJECTION_SCHEMA_VERSION = "loopx_todo_section_projection_v0"
_MARKER_PATTERN = re.compile(
    r"(?m)^<!-- loopx:todo-section-projection-v0 "
    r"role=(?P<role>user|agent|archive) "
    r"provider_revision=(?P<revision>[A-Za-z0-9_.:-]+) "
    r"records_sha256=(?P<digest>[a-f0-9]{64}) -->\r?$"
)


class TodoSectionProjectionError(ValueError):
    """Canonical records or Markdown violate the projection contract."""


@dataclass(frozen=True)
class TodoSectionProjectionResult:
    markdown: str
    changed: bool
    source_sha256: str
    rendered_sha256: str
    narrative_sha256: str
    provider_revision: str
    todo_count: int
    section_record_sha256: dict[str, str]


@dataclass(frozen=True)
class _SectionSpan:
    role: str
    start: int
    end: int


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_records(records: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    canonical: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, value in enumerate(records):
        native = value.get("schema_version") == TODO_DOMAIN_ITEM_SCHEMA_VERSION
        record = canonical_record_fields(
            value,
            fields=(
                TODO_DOMAIN_RECORD_FIELDS
                if native
                else TODO_CANONICAL_READ_RECORD_FIELDS
            ),
            required_fields=(
                TODO_DOMAIN_REQUIRED_FIELDS
                if native
                else TODO_CANONICAL_REQUIRED_READ_FIELDS
            ),
            label=f"canonical Todo projection record {index}",
            reject_unknown=True,
        )
        todo_id = str(record.get("todo_id") or "")
        if todo_id in seen:
            raise TodoSectionProjectionError(f"duplicate canonical Todo id: {todo_id}")
        seen.add(todo_id)
        if record.get("role") not in TODO_SECTION_HEADINGS:
            raise TodoSectionProjectionError(f"Todo {todo_id!r} has invalid role")
        if record.get("archive_state") not in {"active", "archive"}:
            raise TodoSectionProjectionError(
                f"Todo {todo_id!r} has an unsupported archive state"
            )
        canonical_todo_read_record(
            {
                **record,
                "schema_version": TODO_ITEM_SCHEMA_VERSION,
                "source_section": (
                    COMPLETED_WORK_ARCHIVE_HEADING
                    if record.get("archive_state") == "archive"
                    else TODO_SECTION_HEADINGS[str(record["role"])]
                ),
                "index": record.get("index", index + 1),
            },
            reject_unknown=True,
        )
        canonical.append(record)
    return canonical


def _record_sort_key(record: Mapping[str, object]) -> tuple[int, str]:
    raw_index = record.get("index")
    try:
        index = int(raw_index) if isinstance(raw_index, (str, int)) else 2**31 - 1
    except (TypeError, ValueError):
        index = 2**31 - 1
    return index, str(record.get("todo_id") or "")


def _section_spans(markdown: str) -> dict[str, _SectionSpan]:
    lines = markdown.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans: dict[str, _SectionSpan] = {}
    for region in find_todo_regions(lines):
        if region.role in spans:
            raise TodoSectionProjectionError(
                f"active Markdown contains multiple {region.role} Todo sections"
            )
        spans[region.role] = _SectionSpan(region.role, offsets[region.start], offsets[region.end])
    return spans


def _narrative_segments(markdown: str) -> list[str]:
    spans = sorted(_section_spans(markdown).values(), key=lambda span: span.start)
    cursor = 0
    parts: list[str] = []
    for span in spans:
        parts.append(markdown[cursor : span.start])
        cursor = span.end
    parts.append(markdown[cursor:])
    return parts


def _render_record(
    record: Mapping[str, object],
    *,
    include_role: bool = False,
    private_validation: Mapping[str, object] | None = None,
) -> list[str]:
    status = normalize_todo_status(record.get("status")) or TODO_STATUS_OPEN
    text = " ".join(str(record.get("text") or "").strip().split())
    if not text:
        raise TodoSectionProjectionError(
            f"Todo {record.get('todo_id')!r} has empty projection text"
        )
    metadata_values = {
        field: record[field]
        for field in TODO_METADATA_FIELDS
        if field in record and record[field] is not None
    }
    if private_validation is not None:
        metadata_values.update(private_validation)
    if not include_role:
        metadata_values.pop("role", None)
    metadata = format_todo_metadata_line(**metadata_values)
    return [
        f"- [{todo_marker_for_status(status)}] {text}",
        *([metadata] if metadata else []),
    ]


def _render_section(
    *,
    role: str,
    records: list[dict[str, object]],
    provider_revision: str,
    newline: str,
    private_validation: Mapping[str, Mapping[str, object]],
) -> tuple[str, str]:
    digest = _sha256_text(_canonical_json(records))
    heading = (
        COMPLETED_WORK_ARCHIVE_HEADING
        if role == "archive"
        else TODO_SECTION_HEADINGS[role]
    )
    lines = [
        f"## {heading}",
        todo_region_marker(role, "begin"),
        f"<!-- loopx:todo-section-projection-v0 role={role} "
        f"provider_revision={provider_revision} records_sha256={digest} -->",
        "",
    ]
    for record in records:
        lines.extend(_render_record(
            record,
            include_role=role == "archive",
            private_validation=private_validation.get(str(record.get("todo_id") or "")),
        ))
    lines.append(todo_region_marker(role, "end"))
    lines.append("")
    return newline.join(lines), digest


def _replace_existing_sections(
    markdown: str,
    *,
    rendered_sections: Mapping[str, str],
) -> str:
    spans = sorted(_section_spans(markdown).values(), key=lambda value: value.start)
    if not spans:
        raise TodoSectionProjectionError(
            "active Markdown omits required Todo sections: no projection anchor"
        )
    replacements = {span.role: rendered_sections[span.role] for span in spans}
    source_roles = set(replacements)
    first_role = spans[0].role
    last_role = spans[-1].role
    prefix: list[str] = []
    if "user" not in source_roles:
        prefix.append(rendered_sections["user"])
    if "agent" not in source_roles:
        if "user" in source_roles:
            replacements["user"] += rendered_sections["agent"]
        else:
            prefix.append(rendered_sections["agent"])
    if "archive" in rendered_sections and "archive" not in source_roles:
        replacements[last_role] += rendered_sections["archive"]
    if prefix:
        replacements[first_role] = "".join(prefix) + replacements[first_role]

    result = markdown
    for span in reversed(spans):
        result = result[: span.start] + replacements[span.role] + result[span.end :]
    return result


def _parsed_active_records(markdown: str) -> list[dict[str, Any]]:
    fields = parse_active_state_todos(markdown, item_limit=None)
    records: list[dict[str, Any]] = []
    for role in TODO_SECTION_HEADINGS:
        summary = fields.get(f"{role}_todos")
        items = summary.get("items") if isinstance(summary, dict) else []
        for item in sorted(items or [], key=_record_sort_key):
            if isinstance(item, dict) and item.get("archive_state") == "active":
                records.append(canonical_todo_read_record(item, reject_unknown=False))
    return records


def _parsed_archive_records(markdown: str) -> list[dict[str, Any]]:
    lines = markdown.splitlines()
    bounds = archive_section_bounds(lines)
    if bounds is None:
        return []
    records: list[dict[str, Any]] = []
    for item in todo_blocks(
        lines,
        bounds[0],
        bounds[1],
        source_section=COMPLETED_WORK_ARCHIVE_HEADING,
    ):
        if item.get("role") not in TODO_SECTION_HEADINGS:
            raise TodoSectionProjectionError(
                f"archived Todo {item.get('todo_id')!r} omits its source role"
            )
        records.append(
            canonical_todo_read_record(
                project_completion_validation_authority({
                    **item,
                    "schema_version": TODO_ITEM_SCHEMA_VERSION,
                    "archive_state": "archive",
                    "source_section": COMPLETED_WORK_ARCHIVE_HEADING,
                }),
                reject_unknown=False,
            )
        )
    return records


def _projection_record(
    record: Mapping[str, object],
    *,
    display_index: int,
) -> dict[str, object]:
    projected = dict(canonical_todo_read_record(
        {
            **record,
            "schema_version": TODO_ITEM_SCHEMA_VERSION,
            "source_section": (
                COMPLETED_WORK_ARCHIVE_HEADING
                if record.get("archive_state") == "archive"
                else TODO_SECTION_HEADINGS[str(record["role"])]
            ),
            "index": record.get("index", display_index),
        },
        reject_unknown=True,
    ))
    if "decision_scope" in projected:
        # The Markdown codec spells out the optional scope schema version on
        # readback. Normalize that display representation, never the provider
        # record or its digest, before comparing the same semantic scope.
        projected["decision_scope"] = require_todo_decision_scope(projected["decision_scope"])
    return projected


_DERIVED_READ_MODEL_FIELDS = {
    "created_by",
    "last_actor_agent_id",
    "resume_condition",
    "resume_ready",
    "handoff_note",
}


def _private_validation_metadata(
    markdown: str,
) -> dict[str, tuple[dict[str, Any], dict[str, object]]]:
    lines = markdown.splitlines()
    private: dict[str, tuple[dict[str, Any], dict[str, object]]] = {}
    for region in find_todo_regions(lines):
        for item in todo_blocks(
            lines,
            region.start,
            region.body_end,
            role=region.role if region.role in TODO_SECTION_HEADINGS else None,
            source_section=region.heading,
        ):
            todo_id = str(item.get("todo_id") or "")
            declaration = completion_validation_declaration(item)
            if not todo_id or declaration is None:
                continue
            private[todo_id] = _private_validation_entry(declaration)
    return private


def _private_validation_entry(
    declaration: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, object]]:
    normalized = completion_validation_declaration(dict(declaration))
    if normalized is None:
        raise TodoSectionProjectionError("private validation declaration is empty")
    metadata: dict[str, object] = {
        key: value for key, value in normalized.items() if value is not None
    }
    argv = metadata.get("validation_command_argv")
    if isinstance(argv, list):
        metadata["validation_command_argv"] = json.dumps(
            argv,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return normalized, metadata


def _parity_records(records: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {
            field: record[field]
            for field in TODO_CANONICAL_READ_RECORD_FIELDS
            if field in record
            and field not in _DERIVED_READ_MODEL_FIELDS
            and record[field] != []
        }
        for record in records
    ]


def render_canonical_todo_sections(
    markdown: str,
    records: Sequence[Mapping[str, object]],
    *,
    provider_revision: str,
    private_validation_declarations: Mapping[str, Mapping[str, Any]] | None = None,
) -> TodoSectionProjectionResult:
    """Replace only Todo sections and verify deterministic parse/render parity."""

    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", provider_revision):
        raise TodoSectionProjectionError("provider_revision must be a public-safe token")
    canonical = _canonical_records(records)
    private_source = _private_validation_metadata(markdown)
    for todo_id, declaration in (private_validation_declarations or {}).items():
        external = _private_validation_entry(declaration)
        existing = private_source.get(todo_id)
        if existing is not None and (
            completion_validation_declaration_sha256(existing[0])
            != completion_validation_declaration_sha256(external[0])
        ):
            raise TodoSectionProjectionError(
                f"Todo {todo_id!r} has divergent private validation declarations"
            )
        private_source[todo_id] = external
    private_validation: dict[str, Mapping[str, object]] = {}
    for record in canonical:
        todo_id = str(record.get("todo_id") or "")
        required = record.get("completion_validation_required") is True
        digest = record.get("completion_validation_sha256")
        if not required:
            if digest is not None:
                raise TodoSectionProjectionError(
                    f"Todo {todo_id!r} has a validation digest without authority"
                )
            continue
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise TodoSectionProjectionError(
                f"Todo {todo_id!r} requires validation but omits its declaration digest"
            )
        source = private_source.get(todo_id)
        if (
            source is None
            or completion_validation_declaration_sha256(source[0]) != digest
        ):
            raise TodoSectionProjectionError(
                f"Todo {todo_id!r} private validation declaration does not match authority"
            )
        private_validation[todo_id] = source[1]
    source_spans = _section_spans(markdown)
    by_role = {
        role: sorted(
            [
                record
                for record in canonical
                if record.get("role") == role
                and record.get("archive_state") == "active"
            ],
            key=_record_sort_key,
        )
        for role in TODO_SECTION_HEADINGS
    }
    archived = sorted(
        [record for record in canonical if record.get("archive_state") == "archive"],
        key=_record_sort_key,
    )
    newline = "\r\n" if "\r\n" in markdown else "\n"
    rendered_sections: dict[str, str] = {}
    section_digests: dict[str, str] = {}
    for role in TODO_SECTION_HEADINGS:
        rendered_sections[role], section_digests[role] = _render_section(
            role=role,
            records=by_role[role],
            provider_revision=provider_revision,
            newline=newline,
            private_validation=private_validation,
        )
    if archived or "archive" in source_spans:
        rendered_sections["archive"], section_digests["archive"] = _render_section(
            role="archive",
            records=archived,
            provider_revision=provider_revision,
            newline=newline,
            private_validation=private_validation,
        )

    rendered = _replace_existing_sections(
        markdown,
        rendered_sections=rendered_sections,
    )
    before_narrative = "".join(_narrative_segments(markdown))
    after_narrative = "".join(_narrative_segments(rendered))
    if before_narrative != after_narrative:
        raise TodoSectionProjectionError("render changed Markdown outside Todo sections")

    expected_records = [
        _projection_record(record, display_index=index)
        for records_for_section in (by_role["user"], by_role["agent"], archived)
        for index, record in enumerate(records_for_section, 1)
    ]
    expected = _parity_records(expected_records)
    # Validate the generated payload, independently of unrelated document text.
    rendered_payload = "\n".join(rendered_sections.values())
    actual = _parity_records(
        [
            *_parsed_active_records(rendered_payload),
            *_parsed_archive_records(rendered_payload),
        ]
    )
    if _canonical_json(actual) != _canonical_json(expected):
        raise TodoSectionProjectionError("Todo section parse/render parity mismatch")
    second = _replace_existing_sections(rendered, rendered_sections=rendered_sections)
    if second != rendered:
        raise TodoSectionProjectionError("Todo section projection is not idempotent")

    return TodoSectionProjectionResult(
        markdown=rendered,
        changed=rendered != markdown,
        source_sha256=_sha256_text(markdown),
        rendered_sha256=_sha256_text(rendered),
        narrative_sha256=_sha256_text(after_narrative),
        provider_revision=provider_revision,
        todo_count=len(canonical),
        section_record_sha256=section_digests,
    )


def inspect_todo_section_projection(markdown: str) -> dict[str, object]:
    """Return compact marker diagnostics without treating Markdown as truth."""

    markers = [match.groupdict() for match in _MARKER_PATTERN.finditer(markdown)]
    return {
        "schema_version": TODO_SECTION_PROJECTION_SCHEMA_VERSION,
        "section_count": len(markers),
        "sections": markers,
    }


__all__ = [
    "TODO_SECTION_PROJECTION_SCHEMA_VERSION",
    "TodoSectionProjectionError",
    "TodoSectionProjectionResult",
    "inspect_todo_section_projection",
    "render_canonical_todo_sections",
]
