from uuid import uuid4

import pytest

from cygnusx.application.services.report_preview_renderer import render_preview

pytestmark = pytest.mark.unit


def test_interactive_preview_injects_selection_bridge() -> None:
    report_id = uuid4()
    html = render_preview(report_id, "c" * 32, content="<html><body><p>x</p></body></html>", interactive=True)
    assert "cygnusx:report-selection" in html
    assert "mouseup" in html
    assert "sectionOf" in html
    assert "未命名区域" in html
    assert "text.slice(0,4000)" in html
    assert str(report_id) in html


def test_non_interactive_preview_has_no_selection_bridge() -> None:
    html = render_preview(uuid4(), "c" * 32, content="<p>x</p>", interactive=False)
    assert "cygnusx:report-selection" not in html
    assert 'sandbox=""' in html


def test_selection_forwarder_validates_identity_and_length() -> None:
    report_id = uuid4()
    channel = "d" * 32
    html = render_preview(report_id, channel, content="<p>x</p>", interactive=True)
    assert "d.text.length>4000" in html
    assert "d.section.length>80" in html
    assert str(report_id) in html
    assert channel in html
