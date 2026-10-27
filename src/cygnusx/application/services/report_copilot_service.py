"""Server scoped, read only operations for report Copilot sessions."""

from __future__ import annotations

import csv
import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services.report_paths_contract import (
    REPORT_FILE_MAX_BYTES,
    decode_report_paths,
    parse_report_paths,
    read_local_report_file,
)
from cygnusx.application.services.report_snapshot_manifest import open_evidence_file
from cygnusx.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from cygnusx.infrastructure.database.models.report import ReportModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.storage import get_path_factory

REPORT_COPILOT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_report_section",
            "description": "Read bounded plain text from a named section of the bound report.",
            "parameters": {
                "type": "object",
                "properties": {"section": {"type": "string", "maxLength": 80}},
                "required": ["section"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_artifacts",
            "description": "List files registered for the bound report or its verified task.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_project_results",
            "description": "Query a bounded top-N preview from a tabular artifact of the bound report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "maxLength": 80},
                    "artifact": {"type": "string", "maxLength": 240},
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 100},
                    "filters": {
                        "type": "object",
                        "additionalProperties": {"type": "string", "maxLength": 100},
                    },
                },
                "required": ["role"],
                "additionalProperties": False,
            },
        },
    },
]

_MAX_TEXT = 12_000
_MAX_TABLE_BYTES = 2 * 1024 * 1024
_MAX_ARTIFACTS = 2000


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        elif tag.lower() in {"h1", "h2", "h3", "h4", "section", "article", "p", "tr", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1
        elif tag.lower() in {"section", "article", "p", "tr", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class ReportCopilotService:
    """Resolve every operation from an owner checked report binding."""

    def __init__(self, db: AsyncSession, user_id: str, session_id: str) -> None:
        self.db = db
        self.user_id = user_id
        self.session_id = session_id

    async def _bound_report(self) -> tuple[ReportModel, TaskModel | None]:
        from cygnusx.infrastructure.database.models.chat import ChatSessionModel

        session = await self.db.scalar(
            select(ChatSessionModel).where(
                ChatSessionModel.session_id == self.session_id,
                ChatSessionModel.user_id == self.user_id,
                ChatSessionModel.status == "active",
            )
        )
        meta = session.sandbox_meta if session and isinstance(session.sandbox_meta, dict) else {}
        binding = meta.get("report_copilot") if isinstance(meta, dict) else None
        if not isinstance(binding, dict):
            raise AuthorizationError("此会话未绑定报告")
        try:
            report_id = UUID(str(binding.get("report_id")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise AuthorizationError("报告会话绑定无效") from exc
        report = await self.db.scalar(
            select(ReportModel).where(
                ReportModel.id == report_id,
                ReportModel.user_id == UUID(self.user_id),
            )
        )
        if report is None:
            raise NotFoundError("报告不存在或无权访问")
        if report.status != "completed" or report.report_kind == "delivery":
            raise ValidationError("当前报告不可供 Copilot 解读")
        if report.project_user_id is not None and report.project_user_id != UUID(self.user_id):
            raise AuthorizationError("报告元数据归属与当前用户不一致")
        task = await self.db.scalar(
            select(TaskModel).where(
                TaskModel.id == report.task_id,
                TaskModel.user_id == UUID(self.user_id),
            )
        )
        return report, task

    async def metadata(self) -> dict[str, Any]:
        report, task = await self._bound_report()
        params = task.parameters if task and isinstance(task.parameters, dict) else {}
        projection = await self._registered_projection(report, task)
        stats = projection.get("stats", {})
        project = projection.get("project", {})
        groups = (
            stats.get("groups")
            or stats.get("sample_groups")
            or (params.get("groups") or params.get("contrasts") or params.get("sample_groups"))
            if report.report_schema_version == "2.0.0"
            else stats.get("groups") or stats.get("sample_groups")
        )
        raw_metrics = stats.get("core_metrics") or stats.get("metrics") or {}
        metrics = (
            {
                str(key)[:80]: value
                for key, value in list(raw_metrics.items())[:50]
                if isinstance(key, str) and isinstance(value, (str, int, float, bool, type(None)))
            }
            if isinstance(raw_metrics, dict)
            else {}
        )
        project_id = report.project_id
        metadata_status = (
            "legacy_degraded"
            if report.report_schema_version != "2.1.0"
            else "available"
        )
        artifacts = projection.get("files", [])[:_MAX_ARTIFACTS]
        return {
            "report_id": str(report.id),
            "project_id": project_id,
            "scope": "verified_project" if project_id else "report_task_only",
            "flow": report.flow_name or report.flow_id,
            "flow_id": report.flow_id,
            "sample_count": stats.get("total_samples", report.sample_count or (task.sample_count if task else 0)),
            "groups": groups if isinstance(groups, (dict, list)) else None,
            "species": project.get("species") or report.project_species,
            "client": project.get("client") or report.project_client,
            "genome_version": project.get("genome_version") or report.genome_version,
            "pipeline_version": project.get("pipeline_version") or report.pipeline_version,
            "core_metrics": metrics,
            "enrichment": projection.get("enrichment", {}),
            "task_status": task.status if task else None,
            "artifacts": artifacts[:_MAX_ARTIFACTS],
            "metadata_status": metadata_status,
            "metadata_error": report.metadata_error,
        }

    async def _registered_projection(
        self, report: ReportModel, task: TaskModel | None
    ) -> dict[str, Any]:
        if report.report_schema_version == "2.1.0":
            if not report.report_paths_json_path:
                raise ValidationError("报告元数据索引缺失")
            paths_file = Path(report.report_paths_json_path)
            owner_root = get_path_factory().user_root(self.user_id).resolve()
            try:
                paths_file.resolve(strict=True).relative_to(owner_root)  # noqa: ASYNC240
            except (OSError, ValueError) as exc:
                raise AuthorizationError("报告元数据路径不属于当前用户") from exc
            root = paths_file.parent
            try:
                # The JSON is read through the same pinned no-follow FD helper used by P1.
                with open_evidence_file(paths_file) as stream:
                    raw = stream.read(2 * 1024 * 1024 + 1)
                payload = decode_report_paths(raw)
                projection = parse_report_paths(
                    payload,
                    report_id=str(report.id),
                    task_id=str(report.task_id),
                    owner_id=self.user_id,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ValidationError("报告结构化元数据暂不可读取") from exc
            if projection.schema_version != report.report_schema_version:
                raise ValidationError("报告注册表与 JSON schema 版本不一致")
            if list(projection.files) != list(report.files_index or []):
                raise ValidationError("报告注册表与 JSON 文件索引不一致")
            return {
                "project": projection.project,
                "stats": projection.stats,
                "enrichment": projection.enrichment,
                "files": list(projection.files),
                "root": str(root),
            }
        # Legacy 2.0.0 reports retain a clearly marked Task/registry fallback.
        return {
            "project": {
                "project_id": report.project_id,
                "species": report.project_species,
                "client": report.project_client,
                "genome_version": report.genome_version,
                "pipeline_version": report.pipeline_version,
            },
            "stats": dict(report.stats or {}),
            "enrichment": dict(report.enrichment_summary or {}),
            "files": list(report.files_index or []),
            "root": str(Path(report.report_paths_json_path).parent)
            if report.report_paths_json_path
            else None,
        }

    async def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in {"read_report_section", "list_artifacts", "query_project_results"}:
            raise AuthorizationError("Copilot 只允许读取当前报告数据")
        report, task = await self._bound_report()
        if tool_name == "read_report_section":
            return await self._read_section(report, str(args.get("section") or ""))
        if tool_name == "list_artifacts":
            return await self._list_artifacts(report, task)
        return await self._query_table(report, task, args)

    async def _read_section(self, report: ReportModel, requested: str) -> dict[str, Any]:
        if not requested.strip() or len(requested) > 80:
            raise ValidationError("请指定报告章节名称")
        from cygnusx.application.services.report_service import ReportService

        content = await ReportService(self.db).preview_html(report.id, self.user_id, strict=True)
        parser = _VisibleText()
        parser.feed(content)
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        label = requested.strip()
        idx = text.casefold().find(label.casefold())
        if idx < 0:
            return {"section": label, "found": False, "content": "未找到该章节标题。"}
        excerpt = text[idx : idx + _MAX_TEXT]
        return {
            "report_id": str(report.id),
            "section": label,
            "found": True,
            "content": excerpt,
            "truncated": idx + len(excerpt) < len(text),
        }

    async def _list_artifacts(self, report: ReportModel, task: TaskModel | None) -> dict[str, Any]:
        projection = await self._registered_projection(report, task)
        files = projection.get("files", [])
        return {
            "report_id": str(report.id),
            "artifacts": files[:_MAX_ARTIFACTS],
            "truncated": len(files) > _MAX_ARTIFACTS,
            "metadata_status": "legacy_degraded" if report.report_schema_version != "2.1.0" else "available",
        }

    async def _query_table(
        self, report: ReportModel, task: TaskModel | None, args: dict[str, Any]
    ) -> dict[str, Any]:
        if task is None:
            raise ValidationError("该报告没有可核验的分析任务，暂不支持结果表查询")
        projection = await self._registered_projection(report, task)
        requested_role = str(args.get("role") or "").strip()
        requested_name = str(args.get("artifact") or "").strip()
        if not requested_role and not requested_name:
            raise ValidationError("请指定结果文件角色")
        candidates = projection.get("files", [])
        match = next(
            (
                item
                for item in candidates
                if (requested_role and item.get("role") == requested_role)
                or (requested_name and Path(str(item.get("path", ""))).name == requested_name)
            ),
            None,
        )
        if match is None or str(match.get("format", "")).lower() not in {"csv", "tsv"}:
            raise ValidationError("只支持读取报告文件索引中登记的 CSV/TSV 结果")
        root_value = projection.get("root")
        if not isinstance(root_value, str) or not root_value:
            raise ValidationError("该旧报告缺少可读取的文件索引")
        try:
            content = read_local_report_file(
                Path(root_value), str(match["path"]), max_bytes=min(_MAX_TABLE_BYTES, REPORT_FILE_MAX_BYTES)
            ).decode("utf-8-sig", errors="replace")
        except (OSError, ValueError, KeyError) as exc:
            raise ValidationError("报告结果文件不存在或路径无效") from exc
        delimiter = "\t" if str(match["format"]).lower() == "tsv" else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        fields = reader.fieldnames or []
        raw_filters = args.get("filters")
        filters: dict[str, str] = (
            {
                str(key): str(value)
                for key, value in raw_filters.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            if isinstance(raw_filters, dict)
            else {}
        )
        if set(filters) - set(fields):
            raise ValidationError("筛选列不在此结果表中")
        rows: list[dict[str, str]] = []
        raw_top_n = args.get("top_n", 20)
        if isinstance(raw_top_n, bool) or not isinstance(raw_top_n, int):
            raise ValidationError("top_n 必须是整数")
        top_n = max(1, min(100, raw_top_n))
        for row in reader:
            if all(str(row.get(key, "")) == str(value) for key, value in filters.items()):
                rows.append(
                    {key: str(value or "")[:500] for key, value in row.items() if key in fields}
                )
                if len(rows) >= top_n:
                    break
        return {
            "report_id": str(report.id),
            "role": match.get("role"),
            "artifact": Path(str(match["path"])).name,
            "description": match.get("description", ""),
            "columns": fields[:100],
            "rows": rows,
            "truncated": len(content) >= _MAX_TABLE_BYTES,
            "metadata_status": "legacy_degraded" if report.report_schema_version != "2.1.0" else "available",
        }
