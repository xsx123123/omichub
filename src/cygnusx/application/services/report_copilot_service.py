"""Server scoped, read only operations for report Copilot sessions."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cygnusx.application.services.report_copilot_readers import (
    ReportSections,
    matching_files,
    query_table,
    queryable,
    select_table,
)
from cygnusx.application.services.report_paths_contract import (
    decode_report_paths,
    parse_report_paths,
)
from cygnusx.application.services.report_snapshot_manifest import open_evidence_file
from cygnusx.core.config import get_settings
from cygnusx.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from cygnusx.infrastructure.database.models.report import ReportModel
from cygnusx.infrastructure.database.models.task import TaskModel
from cygnusx.infrastructure.storage import get_path_factory

REPORT_COPILOT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_report_section",
            "description": "Read actual heading/body text, excluding navigation/TOC. Use a complete section title; interactive tables must be queried via query_project_results, not their Loading placeholders.",
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
            "description": "Find existing registered files (not newly generated artifacts). Returns paginated items and next_offset; filter role=deg_table/enrichment_table/qc_stats and keyword for a contrast, GO or KEGG. Always use returned path as query artifact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "maxLength": 80},
                    "keyword": {"type": "string", "maxLength": 120},
                    "offset": {"type": "integer", "minimum": 0, "maximum": 2000},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_project_results",
            "description": "Read one registered CSV/TSV or tab-delimited QC TXT. Specify exact artifact path to choose a contrast/direction; role alone is rejected if ambiguous. Supports numeric filters and numerical top-N sort. For pathways use p.adjust<0.05 and sort_by=p.adjust; for DEG use the actual raw/adjusted P and log2FoldChange criteria without conflating them. No file modification or plot generation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "maxLength": 80},
                    "artifact": {"type": "string", "maxLength": 240},
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 100},
                    "columns": {
                        "type": "array",
                        "maxItems": 16,
                        "items": {"type": "string", "maxLength": 100},
                    },
                    "sort_by": {"type": "string", "maxLength": 100},
                    "order": {"type": "string", "enum": ["asc", "desc"]},
                    "numeric_filters": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                key: {"type": "number"}
                                for key in ("lt", "lte", "gt", "gte", "eq", "abs_gt", "abs_gte")
                            },
                            "additionalProperties": False,
                        },
                    },
                    "filters": {
                        "type": "object",
                        "additionalProperties": {"type": "string", "maxLength": 100},
                    },
                },
                "additionalProperties": False,
            },
        },
    },
]


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
                str(key)[:80]: value[:200] if isinstance(value, str) else value
                for key, value in list(raw_metrics.items())[:50]
                if isinstance(key, str) and isinstance(value, (str, int, float, bool, type(None)))
            }
            if isinstance(raw_metrics, dict)
            else {}
        )
        project_id = report.project_id
        metadata_status = (
            "legacy_degraded" if report.report_schema_version != "2.1.0" else "available"
        )
        artifacts = projection.get("files", [])
        readable = [entry for entry in artifacts if queryable(entry)]
        result = {
            "report_id": str(report.id),
            "project_id": project_id,
            "scope": "verified_project"
            if project_id
            else ("external_report_only" if report.external_source_key else "report_task_only"),
            "flow": report.flow_name or report.flow_id,
            "flow_id": report.flow_id,
            "sample_count": stats.get(
                "total_samples", report.sample_count or (task.sample_count if task else 0)
            ),
            "groups": compact_groups(groups),
            "species": project.get("species") or report.project_species,
            "client": project.get("client") or report.project_client,
            "genome_version": project.get("genome_version") or report.genome_version,
            "pipeline_version": project.get("pipeline_version") or report.pipeline_version,
            "core_metrics": metrics,
            "enrichment": compact_enrichment(projection.get("enrichment", {})),
            "group_count": stats.get("group_count"),
            "artifact_count": len(artifacts),
            "queryable_roles": dict(Counter(entry["role"] for entry in readable)),
            "capabilities": {"read_tables": True, "edit_report": False, "execute_code": False},
            "task_status": task.status if task else None,
            "artifact_examples": [
                {"path": entry["path"], "role": entry["role"]} for entry in readable[:6]
            ],
            "artifact_listing": "Use list_artifacts(role, keyword, offset, limit) to find every registered file.",
            "metadata_status": metadata_status,
            "metadata_error": report.metadata_error,
        }
        result["context_truncated"] = False
        while (
            len(json.dumps(result, ensure_ascii=False))
            > get_settings().report_copilot_output_max_chars
        ):
            result["context_truncated"] = True
            if result["artifact_examples"]:
                result["artifact_examples"].pop()
                continue
            if result["core_metrics"]:
                result["core_metrics"].pop(next(reversed(result["core_metrics"])))
                continue
            if result["groups"]:
                group_values = result["groups"]
                if isinstance(group_values, list):
                    group_values.pop()
                else:
                    group_values.pop(next(reversed(group_values)))
                continue
            families = result["enrichment"]
            family = next((value for value in families.values() if value.get("contrasts")), None)
            if family:
                family["contrasts"].pop(next(reversed(family["contrasts"])))
                family["contrasts_truncated"] = True
            elif families:
                families.pop(next(reversed(families)))
            else:
                break
        return result

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
                    task_id=str(report.task_id) if report.task_id else None,
                    owner_id=self.user_id,
                    external_source_key=report.external_source_key,
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
            return await self._list_artifacts(report, task, args)
        return await self._query_table(report, task, args)

    async def _read_section(self, report: ReportModel, requested: str) -> dict[str, Any]:
        if not requested.strip() or len(requested) > 80:
            raise ValidationError("请指定报告章节名称")
        from cygnusx.application.services.report_service import ReportService

        content = await ReportService(self.db).preview_html(report.id, self.user_id, strict=True)

        def read() -> dict[str, Any]:
            parser = ReportSections(get_settings().report_copilot_section_max_chars)
            parser.feed(content)
            return parser.read(requested.strip())

        result = await asyncio.to_thread(read)
        return {"report_id": str(report.id), **result}

    async def _list_artifacts(
        self, report: ReportModel, task: TaskModel | None, args: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        projection = await self._registered_projection(report, task)
        options = args or {}
        files = matching_files(
            projection.get("files", []),
            str(options.get("role") or ""),
            str(options.get("keyword") or ""),
        )
        offset, limit = options.get("offset", 0), options.get("limit", 20)
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset 必须是非负整数")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValidationError("limit 必须在 1–50 之间")
        items = files[offset : offset + limit]
        while (
            len(json.dumps(items, ensure_ascii=False))
            > get_settings().report_copilot_output_max_chars - 1000
            and items
        ):
            items.pop()
        next_offset = offset + len(items) if offset + len(items) < len(files) else None
        return {
            "report_id": str(report.id),
            "items": items,
            "total": len(files),
            "offset": offset,
            "next_offset": next_offset,
            "has_more": next_offset is not None,
            "source": "existing_registered_report_files",
            "generated": False,
            "queryable_roles": dict(Counter(entry["role"] for entry in files if queryable(entry))),
            "metadata_status": "legacy_degraded"
            if report.report_schema_version != "2.1.0"
            else "available",
        }

    async def _query_table(
        self, report: ReportModel, task: TaskModel | None, args: dict[str, Any]
    ) -> dict[str, Any]:
        if task is None and not (
            report.external_source_key and report.report_schema_version == "2.1.0"
        ):
            raise ValidationError("该报告没有可核验的分析任务，暂不支持结果表查询")
        projection = await self._registered_projection(report, task)
        entry = select_table(projection.get("files", []), args)
        root = projection.get("root")
        if not isinstance(root, str) or not root:
            raise ValidationError("报告缺少可读取的文件索引")
        value = await asyncio.to_thread(query_table, Path(root), entry, args)
        return {
            "report_id": str(report.id),
            **value,
            "metadata_status": "legacy_degraded"
            if report.report_schema_version != "2.1.0"
            else "available",
        }


def compact_groups(value: Any) -> dict[str, Any] | list[Any] | None:
    if isinstance(value, list):
        return [str(item)[:160] for item in value[:20]]
    if isinstance(value, dict):
        return {
            str(key)[:80]: (
                [str(item)[:80] for item in item_value[:5]]
                if isinstance(item_value, list)
                else str(item_value)[:160]
            )
            for key, item_value in list(value.items())[:20]
        }
    return None


def compact_enrichment(value: Any) -> dict[str, Any]:
    """Keep thresholds/counts and exact table references, not full term/gene lists."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for name, family in list(value.items())[:4]:
        if not isinstance(family, dict):
            continue
        summary: dict[str, Any] = {
            key: family[key]
            if isinstance(family[key], (bool, int, float, type(None)))
            else str(family[key])[:160]
            for key in ("enabled", "method", "status")
            if key in family
        }
        parameters = family.get("parameters")
        if isinstance(parameters, dict):
            summary["parameters"] = {
                str(key)[:80]: value
                if isinstance(value, (bool, int, float, type(None)))
                else value[:160]
                for key, value in list(parameters.items())[:16]
                if isinstance(value, (str, bool, int, float, type(None)))
            }
        contrasts = family.get("contrasts")
        if isinstance(contrasts, dict):
            summary["contrasts"] = {
                contrast: {
                    direction: {
                        **{
                            key: detail[key]
                            if isinstance(detail[key], (bool, int, float, type(None)))
                            else str(detail[key])[:1024]
                            for key in ("status", "table")
                            if key in detail
                        },
                        "input_term_count": detail.get("term_count")
                        if isinstance(detail.get("term_count"), (int, float))
                        else None,
                        "significance_verified": False,
                    }
                    for direction, detail in list(directions.items())[:2]
                    if isinstance(detail, dict)
                }
                for contrast, directions in list(contrasts.items())[:24]
                if isinstance(directions, dict)
            }
            summary["contrast_count"] = len(contrasts)
            summary["significance_note"] = (
                "input_term_count 不是显著条目数；必须查询表格按实际校正 P 值筛选。"
            )
        result[str(name)] = summary
    return result


def report_tool_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ValidationError):
        return {
            "error": exc.detail,
            "code": exc.code or "REPORT_ARGUMENT_INVALID",
            "next_action": "按提示修正参数；list_artifacts 支持 role/keyword 分页查询。参数或格式错误不代表没有访问权限。",
        }
    if isinstance(exc, (AuthorizationError, NotFoundError)):
        return {
            "error": "报告绑定或访问权限已失效，请重新打开当前报告。",
            "code": "REPORT_ACCESS_DENIED",
        }
    return {"error": "当前报告数据暂不可读取，请稍后重试。", "code": "REPORT_READ_UNAVAILABLE"}
