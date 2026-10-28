"""Bounded, deterministic report reads; no execution, discovery or scope expansion."""

from __future__ import annotations

import csv
import heapq
import io
import json
import math
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from cygnusx.application.services.report_paths_contract import (
    read_local_report_file,
    validate_relative_path,
)
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import ValidationError

ROLE_ALIASES = {
    "diff_expr": "deg_table",
    "differential_expression": "deg_table",
    "deg": "deg_table",
    "enrichment": "enrichment_table",
    "enrichment_go": "enrichment_table",
    "enrichment_kegg": "enrichment_table",
    "go": "enrichment_table",
    "kegg": "enrichment_table",
    "qc": "qc_stats",
}


def queryable(entry: dict[str, Any]) -> bool:
    name = Path(str(entry.get("path", ""))).name.casefold()
    if name.startswith(("md5", "checksum")) or name.endswith((".sha256", ".md5")):
        return False
    fmt = str(entry.get("format", "")).casefold()
    return fmt in {"csv", "tsv"} or (fmt == "txt" and entry.get("role") == "qc_stats")


def matching_files(
    files: list[dict[str, Any]], role: str = "", keyword: str = ""
) -> list[dict[str, Any]]:
    canonical = ROLE_ALIASES.get(role.casefold(), role)
    subtype = (
        "go"
        if role.casefold() in {"go", "enrichment_go"}
        else "kegg"
        if role.casefold() in {"kegg", "enrichment_kegg"}
        else ""
    )
    return [
        entry
        for entry in files
        if (not canonical or entry.get("role") == canonical)
        and (not subtype or f"_{subtype}_" in Path(entry["path"]).name.casefold())
        and (not keyword or keyword.casefold() in entry["path"].casefold())
    ]


def select_table(files: list[dict[str, Any]], args: dict[str, Any]) -> dict[str, Any]:
    role = str(args.get("role") or "").strip()
    name = str(args.get("artifact") or "").strip()
    if not role and not name:
        raise ValidationError(
            "请指定 role 或登记产物的相对路径 artifact", code="REPORT_ARTIFACT_REQUIRED"
        )
    candidates = matching_files(files, role)
    if name:
        try:
            normalized = validate_relative_path(name)
        except ValueError as exc:
            raise ValidationError(
                "artifact 必须为登记的相对路径或文件名", code="REPORT_ARTIFACT_INVALID"
            ) from exc
        # A supplied name always narrows the selection; never OR it with role.
        candidates = [entry for entry in candidates if entry["path"] == normalized]
        if not candidates and "/" not in normalized:
            candidates = [
                entry
                for entry in matching_files(files, role)
                if Path(entry["path"]).name == normalized
            ]
    candidates = [entry for entry in candidates if queryable(entry)]
    if not candidates:
        raise ValidationError(
            "未找到匹配的可查询表格；请用 list_artifacts 按 role/keyword 查找。支持 deg_table、enrichment_table、qc_stats；MD5 清单不是结果表。",
            code="REPORT_TABLE_NOT_FOUND",
        )
    if len(candidates) != 1:
        choices = "、".join(entry["path"] for entry in candidates[:4])
        raise ValidationError(
            f"匹配到 {len(candidates)} 个表格，请指定 artifact 选择对比和方向，例如：{choices}",
            code="REPORT_TABLE_AMBIGUOUS",
        )
    return candidates[0]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def query_table(root: Path, entry: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    try:
        content = read_local_report_file(
            root, entry["path"], max_bytes=settings.report_copilot_table_max_bytes
        ).decode("utf-8-sig", errors="replace")
    except (OSError, ValueError) as exc:
        raise ValidationError(
            "结果文件不可读取、发生变化或超过读取大小限制", code="REPORT_TABLE_UNAVAILABLE"
        ) from exc
    delimiter = "," if entry["format"].casefold() == "csv" else "\t"
    if entry["format"].casefold() == "txt" and "\t" not in content.partition("\n")[0]:
        raise ValidationError(
            "该 TXT 不是有列标题的制表符结果表", code="REPORT_TABLE_FORMAT_UNSUPPORTED"
        )
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    fields = reader.fieldnames or []
    if not fields or len(fields) > 1000 or len(set(fields)) != len(fields):
        raise ValidationError("结果表列标题无效", code="REPORT_TABLE_HEADER_INVALID")
    filters = args.get("filters") or {}
    numeric = args.get("numeric_filters") or {}
    if (
        not isinstance(filters, dict)
        or not isinstance(numeric, dict)
        or (set(filters) | set(numeric)) - set(fields)
    ):
        raise ValidationError("筛选列不在此结果表中", code="REPORT_TABLE_COLUMN_INVALID")
    operators = {"lt", "lte", "gt", "gte", "eq", "abs_gt", "abs_gte"}
    for rules in numeric.values():
        if (
            not isinstance(rules, dict)
            or not rules
            or set(rules) - operators
            or any(isinstance(value, bool) or _number(value) is None for value in rules.values())
        ):
            raise ValidationError(
                "数值筛选仅支持有限数值和 lt/lte/gt/gte/eq/abs_gt/abs_gte",
                code="REPORT_TABLE_FILTER_INVALID",
            )
    top = args.get("top_n", 20)
    if isinstance(top, bool) or not isinstance(top, int):
        raise ValidationError("top_n 必须是整数")
    top = max(1, min(100, top))
    sort_by = str(args.get("sort_by") or "")
    if sort_by and sort_by not in fields:
        raise ValidationError("排序列不在此结果表中", code="REPORT_TABLE_COLUMN_INVALID")
    if args.get("order", "asc") not in {"asc", "desc"}:
        raise ValidationError("order 必须为 asc 或 desc")
    descending = args.get("order") == "desc"
    columns = args.get("columns")
    if columns is not None:
        if (
            not isinstance(columns, list)
            or not columns
            or len(columns) > 16
            or any(not isinstance(column, str) or column not in fields for column in columns)
        ):
            raise ValidationError(
                "columns 必须为当前表的 1–16 个列名", code="REPORT_TABLE_COLUMN_INVALID"
            )
    else:
        priority = [
            "ID",
            "Description",
            "ENSEMBL",
            "Symbol",
            "gene",
            "log2FoldChange",
            "padj",
            "p.adjust",
            "pvalue",
            "qvalue",
            "Count",
            "GeneRatio",
            "FoldEnrichment",
            "RichFactor",
        ]
        columns = [column for column in priority if column in fields]
        columns = fields if len(fields) <= 12 else (columns or fields)[:12]
    matched = 0
    scanned = 0
    limited = False

    def selected() -> Any:
        nonlocal matched, scanned, limited
        for row in reader:
            if scanned >= settings.report_copilot_table_max_rows:
                limited = True
                break
            scanned += 1
            if not all(str(row.get(column, "")) == str(value) for column, value in filters.items()):
                continue
            passes = True
            for column, rules in numeric.items():
                value = _number(row.get(column))
                if value is None:
                    passes = False
                    break
                for operator, raw in rules.items():
                    bound = float(raw)
                    checks = {
                        "lt": value < bound,
                        "lte": value <= bound,
                        "gt": value > bound,
                        "gte": value >= bound,
                        "eq": value == bound,
                        "abs_gt": abs(value) > bound,
                        "abs_gte": abs(value) >= bound,
                    }
                    if not checks[operator]:
                        passes = False
                        break
                if not passes:
                    break
            if not passes:
                continue
            matched += 1
            value = _number(row.get(sort_by)) if sort_by else None
            key = (
                (value is None, -value if descending and value is not None else value or 0, scanned)
                if sort_by
                else (False, 0, scanned)
            )
            yield key, {column: str(row.get(column) or "")[:500] for column in columns}

    try:
        rows = [row for _, row in heapq.nsmallest(top, selected(), key=lambda item: item[0])]
    except csv.Error as exc:
        raise ValidationError(
            "结果表不是有效的 CSV/TSV", code="REPORT_TABLE_FORMAT_UNSUPPORTED"
        ) from exc
    output_truncated = False
    while (
        len(json.dumps(rows, ensure_ascii=False)) > settings.report_copilot_output_max_chars - 2000
        and rows
    ):
        rows.pop()
        output_truncated = True
    return {
        "role": entry["role"],
        "artifact": entry["path"],
        "columns": columns,
        "available_columns": fields[:100],
        "rows": rows,
        "returned_rows": len(rows),
        "matched_rows": matched,
        "scanned_rows": scanned,
        "sort_by": sort_by or None,
        "order": "desc" if descending else "asc",
        "numeric_filters": numeric,
        "truncated": limited or matched > len(rows),
        "row_limit_reached": limited,
        "output_truncated": output_truncated,
        "description": entry.get("description", "")[:500],
    }


@dataclass
class Section:
    level: int
    title: str = ""
    anchor: str = ""
    parts: list[str] = field(default_factory=list)
    length: int = 0
    truncated: bool = False


class ReportSections(HTMLParser):
    """Index actual headings and their bodies; navigation labels never count as sections."""

    def __init__(self, maximum: int) -> None:
        super().__init__(convert_charrefs=True)
        self.maximum = maximum
        self.sections: list[Section] = []
        self.hidden: list[str] = []
        self.heading: Section | None = None
        self.current: Section | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "aside", "header"}:
            self.hidden.append(tag)
        if self.hidden:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.current = Section(level=int(tag[1]), anchor=dict(attrs).get("id") or "")
            self.heading = self.current
            self.sections.append(self.current)

    def handle_endtag(self, tag: str) -> None:
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if self.heading and tag == f"h{self.heading.level}":
            self.heading.title = re.sub(r"\s+", " ", self.heading.title).strip().strip("¶# ")
            self.heading = None

    def handle_data(self, data: str) -> None:
        if self.hidden or self.current is None or not data.strip():
            return
        if self.heading:
            self.heading.title += data
        elif self.current.length < self.maximum:
            text = re.sub(r"\s+", " ", data).strip()
            remaining = self.maximum - self.current.length
            self.current.parts.append(text[:remaining])
            self.current.length += len(text) + 1
            self.current.truncated |= len(text) > remaining
        else:
            self.current.truncated = True

    def read(self, requested: str) -> dict[str, Any]:
        label = requested.casefold().strip()
        matches = [
            (i, section)
            for i, section in enumerate(self.sections)
            if section.title.casefold() == label
        ]
        if not matches:
            matches = [
                (i, section)
                for i, section in enumerate(self.sections)
                if label in section.title.casefold()
            ]
            if len(matches) > 1:
                return {
                    "section": requested,
                    "found": False,
                    "content": "匹配到多个正文标题，请指定完整章节名称。",
                    "available_sections": [section.title for _, section in matches[:40]],
                }
        if not matches:
            return {
                "section": requested,
                "found": False,
                "content": "未找到正文标题，请使用 available_sections 中的名称。",
                "available_sections": [section.title for section in self.sections if section.title][
                    :40
                ],
            }
        # Exact headings beat TOC aliases; ambiguous partial matches require clarification.
        index, section = matches[0]
        parts = [section.title, *section.parts]
        truncated = section.truncated
        for child in self.sections[index + 1 :]:
            if child.level <= section.level:
                break
            parts.extend([child.title, *child.parts])
            truncated |= child.truncated
        text = " ".join(parts)
        return {
            "section": section.title,
            "section_id": section.anchor,
            "found": True,
            "content": text[: self.maximum],
            "truncated": truncated or len(text) > self.maximum,
        }
