"""流程报告交付物自动化审计（报告中心 AI 联动 v2 计划 第二部分）。

- 测试样本根目录默认 ``/data/omichub/Flow_report/``，可用 ``FLOW_REPORT_ROOT`` 覆盖；
  目录不存在时整体 SKIP，不阻塞平台 CI。
- ``delivery_manifest.json`` 是唯一权威清单，不硬编码文件名。
- 源文件只读；测试产物写 ``/tmp/flow_report_test/``（可用 ``FLOW_REPORT_TEST_DIR`` 覆盖）。
- 也可直接运行 ``python tests/test_flow_report.py`` 生成 exploration_log.json /
  test_report.md / issues_found.md 而不走 pytest。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

FLOW_REPORT_ROOT = Path(os.environ.get("FLOW_REPORT_ROOT", "/data/omichub/Flow_report"))
ARTIFACT_DIR = Path(os.environ.get("FLOW_REPORT_TEST_DIR", "/tmp/flow_report_test"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not FLOW_REPORT_ROOT.is_dir(), reason="Flow_report 样本根目录不存在"),
]

STATUS_ORDER = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}


@dataclass
class CheckResult:
    check_id: str
    run: str
    status: str
    detail: str = ""


@dataclass
class RunContext:
    run_dir: Path
    run: str
    manifest: dict[str, Any] = field(default_factory=dict)
    md5_entries: list[tuple[str, str]] = field(default_factory=list)
    paths_sidecar: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    exploration: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 路径折算与校验
# ---------------------------------------------------------------------------


class TraversalError(ValueError):
    """清单路径折算失败（穿越/绝对路径/无法在 run 内定位）。"""


def resolve_manifest_path(run_dir: Path, declared: str, output_location: str = "") -> Path:
    """把 manifest 中的构建机绝对路径折算为 run 根目录内路径并做安全校验。"""
    if "\x00" in declared:
        raise TraversalError("路径包含空字节")
    rel = ""
    if output_location and declared.startswith(output_location.rstrip("/") + "/"):
        rel = declared[len(output_location.rstrip("/")) + 1 :]
    elif "/report_data/" in declared:
        rel = declared.split("/report_data/", 1)[1]
    elif not declared.startswith("/"):
        rel = declared
    else:
        candidate = run_dir / Path(declared).name
        if candidate.exists():
            rel = candidate.name
        else:
            raise TraversalError(f"无法在 run 内定位: {declared}")
    if rel.startswith("/") or ".." in Path(rel).parts:
        raise TraversalError(f"路径穿越: {declared}")
    resolved = (run_dir / rel).resolve()
    root = run_dir.resolve()
    if root not in resolved.parents and resolved != root:
        raise TraversalError(f"路径越出 run 根目录: {declared}")
    return resolved


def collect_relpaths(value: Any) -> Iterator[str]:
    """递归收集 JSON 中疑似相对路径的字符串值。"""
    if isinstance(value, dict):
        for item in value.values():
            yield from collect_relpaths(item)
    elif isinstance(value, list):
        for item in value:
            yield from collect_relpaths(item)
    elif isinstance(value, str) and value.startswith(("data/", "./data/")):
        yield value[2:] if value.startswith("./") else value


# ---------------------------------------------------------------------------
# 探索阶段
# ---------------------------------------------------------------------------


def explore_run(run_dir: Path) -> RunContext:
    ctx = RunContext(run_dir=run_dir, run=run_dir.name)
    tree: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        tree.append(str(path.relative_to(run_dir)) + ("/" if path.is_dir() else ""))
        if len(tree) >= 500:
            tree.append("... (truncated)")
            break
    ctx.exploration["tree"] = tree
    manifest_path = run_dir / "delivery_manifest.json"
    if manifest_path.is_file():
        ctx.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ctx.exploration["manifest_meta"] = ctx.manifest.get("meta", {})
        ctx.exploration["manifest_file_count"] = len(ctx.manifest.get("files", {}))
    md5_path = run_dir / "delivery_manifest.md5"
    if md5_path.is_file():
        for line in md5_path.read_text(encoding="utf-8").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{32}", parts[0]):
                ctx.md5_entries.append((parts[0].lower(), parts[1].strip()))
        ctx.exploration["md5_entry_count"] = len(ctx.md5_entries)
    for name, attr in (("report.paths.json", "paths_sidecar"), ("project_summary.json", "summary")):
        path = run_dir / name
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            setattr(ctx, attr, data)
            ctx.exploration[f"{name}_keys"] = list(data.keys()) if isinstance(data, dict) else []
    for html_path in sorted(run_dir.glob("*.html")):
        head = html_path.open(encoding="utf-8", errors="replace").read(4000)
        ctx.exploration[f"{html_path.name}_head"] = head[:2000]
        ctx.exploration[f"{html_path.name}_size"] = html_path.stat().st_size
    return ctx


# ---------------------------------------------------------------------------
# A. 清单完整性
# ---------------------------------------------------------------------------


def check_manifest(ctx: RunContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    run = ctx.run
    if not ctx.manifest:
        return [CheckResult("A-1", run, "FAIL", "delivery_manifest.json 缺失或不可解析")]
    meta = ctx.manifest.get("meta")
    files = ctx.manifest.get("files")
    if not isinstance(meta, dict) or not isinstance(files, dict) or not files:
        results.append(CheckResult("A-1", run, "FAIL", "manifest 缺少 meta/files 结构"))
    else:
        results.append(CheckResult("A-1", run, "PASS", f"{len(files)} 个声明文件"))
        output_location = str(meta.get("output_location", ""))
        missing: list[str] = []
        rebased: set[str] = set()
        for name, declared in files.items():
            try:
                resolved = resolve_manifest_path(ctx.run_dir, str(declared), output_location)
                rebased.add(str(resolved))
                if not resolved.exists():
                    missing.append(name)
            except TraversalError as exc:
                missing.append(f"{name} ({exc})")
        status = "PASS" if not missing else "FAIL"
        results.append(
            CheckResult("A-2", run, status, "全部存在" if not missing else f"缺失 {len(missing)}: {missing[:5]}")
        )
        declared_set = rebased
        orphans = []
        for path in ctx.run_dir.rglob("*"):
            if path.is_dir():
                continue
            if str(path) not in declared_set and path.name not in {
                "delivery_manifest.json",
                "delivery_manifest.md5",
                "report.paths.json",
                "project_summary.json",
            } and not path.name.endswith((".pdf", ".html")):
                orphans.append(str(path.relative_to(ctx.run_dir)))
        results.append(
            CheckResult(
                "A-3",
                run,
                "WARN" if orphans else "PASS",
                f"{len(orphans)} 个孤儿文件: {orphans[:10]}" if orphans else "无孤儿文件",
            )
        )
    if not ctx.md5_entries:
        results.append(CheckResult("A-4", run, "FAIL", "delivery_manifest.md5 缺失或为空"))
    else:
        mismatched: list[str] = []
        absent: list[str] = []
        directories: list[str] = []
        for expected, rel in ctx.md5_entries:
            target = ctx.run_dir / rel
            if target.is_dir():
                directories.append(rel)
                continue
            if not target.is_file():
                absent.append(rel)
                continue
            actual = hashlib.md5(target.read_bytes()).hexdigest()  # noqa: S324
            if actual != expected:
                mismatched.append(f"{rel} 期望 {expected} 实际 {actual}")
        problems = [f"缺失: {m}" for m in absent] + mismatched
        if problems:
            status, detail = "FAIL", "; ".join(problems[:5])
        elif directories:
            status = "WARN"
            detail = f"{len(directories)} 条清单指向目录无法校验 md5: {directories[:3]}"
        else:
            status, detail = "PASS", f"{len(ctx.md5_entries)} 条全部一致"
        results.append(CheckResult("A-4", run, status, detail))
    return results


# ---------------------------------------------------------------------------
# B. 索引与报告文件
# ---------------------------------------------------------------------------


def check_index_and_reports(ctx: RunContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    run = ctx.run
    if not ctx.paths_sidecar:
        results.append(CheckResult("B-5", run, "FAIL", "report.paths.json 缺失或不可解析"))
    else:
        missing = [
            rel for rel in collect_relpaths(ctx.paths_sidecar) if not (ctx.run_dir / rel).exists()
        ]
        results.append(
            CheckResult(
                "B-5",
                run,
                "PASS" if not missing else "FAIL",
                "引用路径全部存在" if not missing else f"缺失 {len(missing)}: {missing[:5]}",
            )
        )
    pdfs = sorted(ctx.run_dir.glob("*.pdf"))
    if not pdfs:
        results.append(CheckResult("B-6", run, "WARN", "未发现 PDF 报告"))
    else:
        try:
            import pdfplumber
        except ImportError:
            results.append(CheckResult("B-6", run, "SKIP", "未安装 pdfplumber"))
        else:
            problems = []
            for pdf in pdfs:
                try:
                    with pdfplumber.open(pdf) as doc:
                        if not doc.pages:
                            problems.append(f"{pdf.name}: 0 页")
                            continue
                        if not (doc.pages[0].extract_text() or "").strip():
                            problems.append(f"{pdf.name}: 首页无文本")
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"{pdf.name}: {exc}")
            results.append(
                CheckResult(
                    "B-6",
                    run,
                    "PASS" if not problems else "FAIL",
                    f"{len(pdfs)} 个 PDF 可读" if not problems else "; ".join(problems),
                )
            )
    htmls = sorted(ctx.run_dir.glob("*.html"))
    if not htmls:
        results.append(CheckResult("B-7", run, "WARN", "未发现 HTML 报告"))
    else:
        external = []
        for html_path in htmls:
            head = html_path.open(encoding="utf-8", errors="replace").read(200_000)
            for match in re.finditer(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', head):
                external.append(f"{html_path.name}: {match.group(1)}")
        results.append(
            CheckResult(
                "B-7",
                run,
                "WARN" if external else "PASS",
                f"外链 {len(external)} 处: {external[:5]}" if external else "自包含（前 200KB 无外链）",
            )
        )
        import importlib.util

        if importlib.util.find_spec("playwright") is None:
            results.append(CheckResult("B-7-headless", run, "SKIP", "未安装 Playwright，跳过无头渲染校验"))
    return results


# ---------------------------------------------------------------------------
# C. 数据一致性
# ---------------------------------------------------------------------------


def _csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8", errors="replace") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def check_consistency(ctx: RunContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    run = ctx.run
    summary = ctx.summary
    if not summary:
        return [CheckResult("C-8", run, "FAIL", "project_summary.json 缺失或不可解析")]
    required = {"schema_version", "project_meta", "stats", "input_files", "enrichment"}
    missing_keys = sorted(required - set(summary))
    enrichment = summary.get("enrichment", {})
    modules = [key for key in ("go", "kegg") if isinstance(enrichment.get(key), dict)]
    if missing_keys or not modules:
        results.append(
            CheckResult("C-8", run, "FAIL", f"缺键 {missing_keys} 或无 go/kegg 分区")
        )
    else:
        results.append(CheckResult("C-8", run, "PASS", f"模块分区: {', '.join(modules)}"))

    samples: list[tuple[str, bool, str]] = []
    stats = summary.get("stats", {})
    sample_file = summary.get("input_files", {}).get("sample_file", "")
    total = stats.get("total_samples")
    sample_path = ctx.run_dir / str(sample_file)
    if isinstance(total, int) and sample_path.is_file():
        actual = _csv_row_count(sample_path)
        ok = actual == total
        samples.append((f"total_samples 声明 {total} vs sample.csv {actual} 行", ok, "exact"))
    checked = 0
    for module in modules:
        contrasts = enrichment[module].get("contrasts", {})
        for contrast_name, directions in contrasts.items():
            if checked >= 4:
                break
            for direction, entry in directions.items():
                if checked >= 4:
                    break
                if entry.get("status") != "available" or not entry.get("table"):
                    continue
                table = ctx.run_dir / str(entry["table"])
                declared = entry.get("term_count")
                if not table.is_file() or not isinstance(declared, int):
                    continue
                actual = _csv_row_count(table)
                samples.append(
                    (
                        f"{module}.{contrast_name}.{direction} term_count {declared} vs {table.name} {actual} 行",
                        actual == declared,
                        "exact",
                    )
                )
                checked += 1
                terms = entry.get("terms") or []
                if terms and "pvalue" in terms[0]:
                    with table.open(encoding="utf-8", errors="replace") as handle:
                        header = handle.readline().strip().split(",")
                        row = handle.readline().strip().split(",")
                    if "pvalue" in header and len(row) > header.index("pvalue"):
                        try:
                            csv_p = float(row[header.index("pvalue")])
                            json_p = float(terms[0]["pvalue"])
                            ok = json_p == 0 or abs(csv_p - json_p) <= 1e-6 * max(1.0, abs(json_p))
                            samples.append(
                                (f"{module}.{contrast_name}.{direction} 首行 pvalue {json_p} vs csv {csv_p}", ok, "1e-6")
                            )
                        except (ValueError, IndexError):
                            pass
    if not samples:
        results.append(CheckResult("C-9", run, "SKIP", "无可抽样的统计量"))
    else:
        failures = [name for name, ok, _ in samples if not ok]
        results.append(
            CheckResult(
                "C-9",
                run,
                "PASS" if not failures else "FAIL",
                f"抽样 {len(samples)} 项全部一致" if not failures else "; ".join(failures[:5]),
            )
        )
    missing_refs = [rel for rel in collect_relpaths(summary) if not (ctx.run_dir / rel).exists()]
    results.append(
        CheckResult(
            "C-10",
            run,
            "PASS" if not missing_refs else "FAIL",
            "JSON 引用路径全部有效" if not missing_refs else f"无效 {len(missing_refs)}: {missing_refs[:5]}",
        )
    )
    return results


# ---------------------------------------------------------------------------
# 汇总入口
# ---------------------------------------------------------------------------


def audit_run(run_dir: Path) -> tuple[RunContext, list[CheckResult]]:
    ctx = explore_run(run_dir)
    results = check_manifest(ctx) + check_index_and_reports(ctx) + check_consistency(ctx)
    results.append(CheckResult("D-11", ctx.run, "SKIP", "无重跑入口，可复现性重放跳过"))
    return ctx, results


def audit_all(root: Path) -> tuple[dict[str, RunContext], list[CheckResult]]:
    contexts: dict[str, RunContext] = {}
    results: list[CheckResult] = []
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        ctx, run_results = audit_run(run_dir)
        contexts[ctx.run] = ctx
        results.extend(run_results)
    return contexts, results


def write_outputs(contexts: dict[str, RunContext], results: list[CheckResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    exploration = {run: ctx.exploration for run, ctx in contexts.items()}
    (out_dir / "exploration_log.json").write_text(
        json.dumps(exploration, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = ["# 流程报告交付物测试报告", ""]
    by_run: dict[str, list[CheckResult]] = {}
    for result in results:
        by_run.setdefault(result.run, []).append(result)
    for run, items in by_run.items():
        lines.append(f"## {run}")
        lines.append("")
        lines.append("| 检查项 | 状态 | 说明 |")
        lines.append("|---|---|---|")
        for item in sorted(items, key=lambda r: (STATUS_ORDER[r.status], r.check_id)):
            lines.append(f"| {item.check_id} | {item.status} | {item.detail[:200]} |")
        lines.append("")
    failures = [r for r in results if r.status == "FAIL"]
    lines.append(f"## 汇总\n\n共 {len(results)} 项：FAIL {len(failures)}，"
                 f"WARN {sum(1 for r in results if r.status == 'WARN')}，"
                 f"SKIP {sum(1 for r in results if r.status == 'SKIP')}，"
                 f"PASS {sum(1 for r in results if r.status == 'PASS')}。")
    (out_dir / "test_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures:
        issues = ["# 疑似交付流程问题", ""]
        for item in failures:
            issues.append(f"## {item.run} / {item.check_id}")
            issues.append(f"- 现象：{item.detail}")
            issues.append("- 建议排查：对应流程的交付清单生成与文件落盘环节")
            issues.append("")
        (out_dir / "issues_found.md").write_text("\n".join(issues), encoding="utf-8")


# ---------------------------------------------------------------------------
# pytest 入口（A–D）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def audit() -> tuple[dict[str, RunContext], list[CheckResult]]:
    contexts, results = audit_all(FLOW_REPORT_ROOT)
    write_outputs(contexts, results, ARTIFACT_DIR)
    return contexts, results


def _statuses(results: list[CheckResult], prefix: str) -> list[CheckResult]:
    return [r for r in results if r.check_id.startswith(prefix)]


def _assert_or_report(results: list[CheckResult], prefix: str) -> None:
    """存量审计发现默认 xfail 报告（不阻塞 make test），FLOW_REPORT_STRICT=1 时硬失败。"""
    failures = [r for r in _statuses(results, prefix) if r.status == "FAIL"]
    if not failures:
        return
    detail = "; ".join(f"{r.run}/{r.check_id}: {r.detail}" for r in failures)
    if os.environ.get("FLOW_REPORT_STRICT") == "1":
        pytest.fail(detail)
    pytest.xfail(f"存量交付问题待流程修复（详见 /tmp/flow_report_test/test_report.md）: {detail}")


def test_manifest_integrity(audit: tuple[dict[str, RunContext], list[CheckResult]]) -> None:
    _, results = audit
    _assert_or_report(results, "A-")


def test_index_and_report_files(audit: tuple[dict[str, RunContext], list[CheckResult]]) -> None:
    _, results = audit
    _assert_or_report(results, "B-")


def test_data_consistency(audit: tuple[dict[str, RunContext], list[CheckResult]]) -> None:
    _, results = audit
    _assert_or_report(results, "C-")


# ---------------------------------------------------------------------------
# F. 测试自证（防假绿）
# ---------------------------------------------------------------------------


def _first_run_dir() -> Path:
    runs = sorted(p for p in FLOW_REPORT_ROOT.iterdir() if p.is_dir())
    if not runs:
        pytest.skip("无可用样本 run")
    return runs[0]


def test_selfproof_missing_file_detected(tmp_path: Path) -> None:
    source = _first_run_dir()
    target = tmp_path / source.name
    shutil.copytree(source, target)
    ctx = explore_run(target)
    victim_rel = next(rel for _, rel in ctx.md5_entries if (target / rel).is_file())
    (target / victim_rel).unlink()
    results = check_manifest(ctx)
    assert any(r.check_id == "A-4" and r.status == "FAIL" for r in results), "删文件后 A-4 未检出"


def test_selfproof_tampered_summary_detected(tmp_path: Path) -> None:
    source = _first_run_dir()
    target = tmp_path / source.name
    shutil.copytree(source, target)
    summary_path = target / "project_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    stats = summary.get("stats", {})
    if isinstance(stats.get("total_samples"), int):
        stats["total_samples"] += 1
        summary_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    else:
        pytest.skip("summary 无 total_samples 可篡改")
    ctx = explore_run(target)
    results = check_consistency(ctx)
    assert any(r.check_id == "C-9" and r.status == "FAIL" for r in results), "篡改后 C-9 未检出"


def test_selfproof_traversal_rejected(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for bad in ("../etc/passwd", "/etc/passwd", "data/../../escape.txt", "a\x00b"):
        with pytest.raises(TraversalError):
            resolve_manifest_path(run_dir, bad, "")


# ---------------------------------------------------------------------------
# 直接运行入口
# ---------------------------------------------------------------------------


def main() -> int:
    if not FLOW_REPORT_ROOT.is_dir():
        print(f"样本根目录不存在: {FLOW_REPORT_ROOT}")
        return 1
    contexts, results = audit_all(FLOW_REPORT_ROOT)
    write_outputs(contexts, results, ARTIFACT_DIR)
    for result in results:
        print(f"[{result.status}] {result.run} {result.check_id} {result.detail[:120]}")
    failures = sum(1 for r in results if r.status == "FAIL")
    print(f"\n产物输出: {ARTIFACT_DIR}（exploration_log.json / test_report.md"
          f"{' / issues_found.md' if failures else ''}）")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main() if not sys.argv[1:] else subprocess.call([sys.executable, "-m", "pytest", __file__, *sys.argv[1:]]))
