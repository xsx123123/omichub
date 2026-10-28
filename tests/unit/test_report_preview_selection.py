import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from uuid import uuid4

import pytest

from cygnusx.application.services.report_preview_renderer import preview_csp, render_preview

pytestmark = pytest.mark.unit


def test_external_embedded_resources_retain_network_and_origin_isolation() -> None:
    policy = preview_csp(embedded_resources=True)
    assert "'unsafe-eval'" in policy  # Required by embedded DataTables callbacks.
    assert "'unsafe-eval'" not in preview_csp()
    assert "connect-src 'none'" in policy and "default-src 'none'" in policy
    assert "allow-same-origin" not in policy and "https:" not in policy
    assert "form-action 'none'" in policy


def test_selection_bridge_executes_and_forwards_only_current_report() -> None:
    """Execute generated JavaScript: substring assertions cannot detect syntax errors."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the preview bridge")

    class FrameParser(HTMLParser):
        srcdoc = ""

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "iframe":
                self.srcdoc = dict(attrs).get("srcdoc") or ""

    report_id = uuid4()
    channel = "d" * 32
    rendered = render_preview(
        report_id, channel, content="<h1>QC</h1><p>15 samples</p>", interactive=True
    )
    parser = FrameParser()
    parser.feed(rendered)
    inner_scripts = re.findall(r"<script>(.*?)</script>", parser.srcdoc, re.S)
    outer_scripts = re.findall(r"<script>(.*?)</script>", rendered, re.S)
    program = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const scripts = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const events = {}, listeners = {}, forwarded = [];
const innerWindow = {}, platform = {};
const heading = {textContent: 'QC', compareDocumentPosition: () => 4,
  scrollIntoView: () => { heading.scrolled = true; }};
const outerEvents = {};
const outer = {
  parent: {postMessage: data => forwarded.push(data)},
  document: {querySelector: () => ({contentWindow: innerWindow})},
  window: {frames: [innerWindow], addEventListener: (type, fn) => {
    (outerEvents[type] ||= []).push(fn);
  }},
};
vm.createContext(outer);
for (const source of scripts.outer) vm.runInContext(source, outer);
const inner = {
  parent: {postMessage: data => {
    for (const fn of outerEvents.message) fn({source: innerWindow, data});
  }},
  window: {addEventListener: (type, fn) => { events[type] = fn; },
    getSelection: () => ({isCollapsed: false, rangeCount: 1, toString: () => '15 samples',
      getRangeAt: () => ({startContainer: {}, getBoundingClientRect: () => ({right: 42, bottom: 24})})})},
  document: {addEventListener: (type, fn) => { listeners[type] = fn; },
    querySelectorAll: () => [heading]},
  Node: {DOCUMENT_POSITION_CONTAINED_BY: 16, DOCUMENT_POSITION_FOLLOWING: 4},
  setTimeout: fn => fn(),
};
vm.createContext(inner);
for (const source of scripts.inner) vm.runInContext(source, inner);
listeners.mouseup();
assert.equal(forwarded.length, 1);
assert.equal(forwarded[0].text, '15 samples');
assert.equal(forwarded[0].section, 'QC');
assert.equal(forwarded[0].x, 42);
assert.equal(forwarded[0].reportId, scripts.reportId);
const valid = forwarded[0];
for (const data of [{...valid, reportId: 'other'}, {...valid, channel: 'other'},
  {...valid, text: 'x'.repeat(4001)}]) {
  for (const fn of outerEvents.message) fn({source: innerWindow, data});
}
for (const fn of outerEvents.message) fn({source: platform, data: valid});
assert.equal(forwarded.length, 1);
events.message({source: inner.parent, origin: 'null', data: {
  type: 'cygnusx:report-section', reportId: scripts.reportId, channel: scripts.channel, section: 'QC'
}});
assert.equal(heading.scrolled, true);
"""
    result = subprocess.run(
        [node, "-e", program],
        input=json.dumps({
            "inner": inner_scripts, "outer": outer_scripts,
            "reportId": str(report_id), "channel": channel,
        }),
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr


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
