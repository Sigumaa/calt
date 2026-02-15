from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any


def _stringify(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def render_kv_panel(title: str, rows: Sequence[tuple[str, Any]]) -> str:
    lines = [f"{label}: {_stringify(value)}" for label, value in rows]
    width = max([len(title), *(len(line) for line in lines), 1])
    top = f"+-[{title}]-" + ("-" * max(width - len(title), 0)) + "+"
    body = [f"| {line.ljust(width)} |" for line in lines] or [f"| {'-'.ljust(width)} |"]
    bottom = "+" + ("-" * (width + 2)) + "+"
    return "\n".join([top, *body, bottom])


def render_table(title: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    normalized_rows = [[_stringify(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in normalized_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def build_row(values: Sequence[str]) -> str:
        padded = [value.ljust(widths[index]) for index, value in enumerate(values)]
        return "| " + " | ".join(padded) + " |"

    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    header_row = build_row(list(headers))
    data_rows = [build_row(row) for row in normalized_rows]

    lines = [title, separator, header_row, separator, *data_rows, separator]
    return "\n".join(lines)


def compose_sections(sections: Sequence[str]) -> str:
    return "\n\n".join(section for section in sections if section.strip())
