from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class _MarkdownCell(str):
    pass


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def markdown_scalar(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()


def markdown_code(value: Any) -> str:
    return _MarkdownCell(f"`{markdown_scalar(value)}`")


def markdown_table_row(cells: Iterable[Any]) -> str:
    rendered = (
        str(cell) if isinstance(cell, _MarkdownCell) else markdown_scalar(cell)
        for cell in cells
    )
    return "| " + " | ".join(rendered) + " |"


def markdown_table_separator(column_count: int) -> str:
    if column_count < 1:
        raise ValueError("markdown table must have at least one column")
    return markdown_table_row(["---"] * column_count)
