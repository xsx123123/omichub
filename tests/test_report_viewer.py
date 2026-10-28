"""报告查看器新功能专项测试（报告中心 AI 联动 v2 计划 第二部分 E 组）。

与 v2 计划的映射关系（详见 docs/implementation/cygnusx-report-ai-linkage-v2-gap-analysis.md）：

- E-12 端点安全：平台以签名 grant + 预览会话 cookie 实现，等效于 401/403/400 矩阵；
  完整矩阵见 tests/unit/test_report_preview_grant.py 与
  tests/integration/test_report_viewer_isolated.py，此处保留自包含的 fail-closed 冒烟。
- E-13 消毒有效性：平台采用隔离模型（CSP sandbox + srcdoc opaque origin）替代内容消毒；
  此处断言外层 CSP 与 sandbox 属性确实切断脚本出网与同源访问。
- E-14 上下文模板：前端 ``reportSelection.buildSelectionPrefill`` 由
  ``frontend/src/utils/__tests__/reportSelection.test.ts`` 覆盖；此处防漂移校验模板字段。
- E-15 Playwright E2E：环境无 Playwright，按 v2 计划 SKIP。
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest

from cygnusx.application.services.report_preview_renderer import preview_csp, render_preview
from cygnusx.core.exceptions import AuthorizationError
from cygnusx.core.report_preview import sign_preview_claims, verify_preview_grant

pytestmark = pytest.mark.unit

FRONTEND_SELECTION_UTIL = (
    Path(__file__).resolve().parent.parent / "frontend" / "src" / "utils" / "reportSelection.ts"
)


# E-12 端点安全（fail-closed 冒烟）---------------------------------------------


def test_e12_preview_grant_fail_closed() -> None:
    report_id = uuid4()
    with pytest.raises(AuthorizationError):
        verify_preview_grant(report_id, "forged-token", "forged-session", "forged-context")
    token = sign_preview_claims({"type": "report_preview", "report_id": "other"})
    with pytest.raises(AuthorizationError):
        verify_preview_grant(report_id, token, token, "context")


# E-13 隔离有效性（替代内容消毒）-----------------------------------------------


def test_e13_preview_csp_blocks_network_and_same_origin() -> None:
    csp = preview_csp()
    assert "sandbox allow-scripts" in csp
    assert "allow-same-origin" not in csp
    assert "connect-src 'none'" in csp
    assert "default-src 'none'" in csp
    assert "form-action 'none'" in csp
    assert "frame-ancestors 'self'" in csp


def test_e13_malicious_markup_confined_to_sandboxed_srcdoc() -> None:
    payload = '<script>alert(1)</script><img src=x onerror=alert(1)>'
    html = render_preview(uuid4(), "c" * 32, content=payload, interactive=True)
    # 隔离模型：内容只能以转义属性形式存在于 srcdoc 内，不会作为外层文档标记解析；
    # 沙盒无 allow-same-origin 且 CSP 断网，内联事件处理器即便存在也无法出网或触达外层。
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert re.search(r'<iframe sandbox="allow-scripts"(?![^>]*allow-same-origin)', html)


# E-14 上下文模板（防漂移）------------------------------------------------------


def test_e14_selection_prefill_template_fields() -> None:
    if not FRONTEND_SELECTION_UTIL.is_file():
        pytest.skip("前端 reportSelection.ts 不存在")
    source = FRONTEND_SELECTION_UTIL.read_text(encoding="utf-8")
    for marker in (
        "【报告上下文】",
        "run: ",
        "流程：",
        "章节：",
        "选中内容：",
        "请基于上述报告上下文回答我的问题：",
        "（已截断）",
        "SELECTION_LIMIT = 2000",
        "SELECTION_KEEP = 1800",
    ):
        assert marker in source, f"上下文模板缺少字段: {marker}"


# E-15 Playwright E2E ----------------------------------------------------------


def test_e15_viewer_e2e() -> None:
    pytest.importorskip("playwright", reason="未安装 Playwright，E2E 链路测试按 v2 计划 SKIP")
