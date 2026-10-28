"""Wrap immutable report bytes in an isolated viewer and a trusted load bridge."""

import html
import json
from uuid import UUID


def preview_csp() -> str:
    # srcdoc inherits this policy. No remote scripts, requests, forms, popups or
    # same-origin privileges; the nested report has its own sandbox as well.
    return (
        "sandbox allow-scripts; default-src 'none'; "
        "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data: blob:; font-src data:; media-src data: blob:; "
        "frame-src 'self' about:; connect-src 'none'; object-src 'none'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
    )


def render_preview(
    report_id: UUID,
    channel: str,
    *,
    content: str = "",
    interactive: bool = False,
    error_status: int | None = None,
) -> str:
    """Only the outer bridge runs for evidence reports; their own scripts stay disabled."""
    event = json.dumps(
        {
            "type": "cygnusx:report-preview",
            "reportId": str(report_id),
            "channel": channel,
            "status": error_status or 200,
        }
    ).replace("<", "\\u003c")
    sandbox = "allow-scripts" if interactive else ""
    if interactive:
        inner_bridge = (
            "<script>(function(){const id="
            + json.dumps(str(report_id))
            + ";const channel="
            + json.dumps(channel)
            + "window.addEventListener('message',e=>{const d=e.data;"
            + "if(e.source!==parent||e.origin!=='null'||!d||d.type!=='cygnusx:report-section'"
            + "||d.reportId!==id||d.channel!==channel||typeof d.section!=='string'||d.section.length>80)return;"
            + "const h=[...document.querySelectorAll('h1,h2,h3,h4,[role=heading]')]"
            + ".find(x=>(x.textContent||'').trim()===d.section);"
            + "if(h)h.scrollIntoView({behavior:'smooth',block:'start'})});"
            # --- selection capture: report -> platform ----------------------
            + "const HEADINGS='h1,h2,h3,h4,[role=heading],.section-title,.panel-title,[data-section]';"
            + "function sectionOf(node){let best=null;"
            + "for(const h of document.querySelectorAll(HEADINGS)){"
            + "const p=h.compareDocumentPosition(node);"
            + "if(p&Node.DOCUMENT_POSITION_CONTAINED_BY||p&Node.DOCUMENT_POSITION_FOLLOWING)best=h;"
            + "else break}"
            + "if(best){const t=(best.textContent||'').trim();if(t)return t.slice(0,80)}"
            + "const el=node.nodeType===1?node:node.parentElement;"
            + "const table=el&&el.closest?el.closest('table'):null;"
            + "const cap=el&&el.closest?(el.closest('caption')||(table?table.querySelector('caption,th'):null)):null;"
            + "if(cap){const t=(cap.textContent||'').trim();if(t)return t.slice(0,80)}"
            + "return '未命名区域'}"
            + "function emit(){const sel=window.getSelection();"
            + "if(!sel||sel.isCollapsed||!sel.rangeCount)return;"
            + "const text=(sel.toString()||'').trim();if(!text)return;"
            + "const range=sel.getRangeAt(0);const rect=range.getBoundingClientRect();"
            + "parent.postMessage({type:'cygnusx:report-selection',reportId:id,channel:channel,"
            + "text:text.slice(0,4000),section:sectionOf(range.startContainer),"
            + "x:rect.right,y:rect.bottom},'*')}"
            + "document.addEventListener('mouseup',()=>setTimeout(emit,0));"
            + "document.addEventListener('keyup',e=>{if(e.key==='Shift'||e.shiftKey)setTimeout(emit,0)});})();</script>"
        )
        lower_content = content.lower()
        body_end = lower_content.rfind("</body>")
        content = (
            content[:body_end] + inner_bridge + content[body_end:]
            if body_end >= 0
            else content + inner_bridge
        )
    section_bridge = ""
    if interactive:
        section_bridge = (
            "<script>(function(){const f=document.querySelector('iframe');"
            "window.addEventListener('message',e=>{const d=e.data;"
            "if(e.source!==parent||e.origin!=='null'||!d||"
            "d.type!=='cygnusx:report-section'||d.reportId!=="
            + json.dumps(str(report_id))
            + "||d.channel!=="
            + json.dumps(channel)
            + "||typeof d.section!=='string'||d.section.length>80||!f||!f.contentWindow)return;"
            "f.contentWindow.postMessage(d,'*')});})();</script>"
        )
    frame = (
        f'<iframe sandbox="{sandbox}" referrerpolicy="no-referrer" '
        f'title="报告内容" srcdoc="{html.escape(content, quote=True)}"></iframe>' + section_bridge
        if error_status is None
        else "<p>报告当前无法预览，请返回平台重试或下载。</p>"
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="referrer" content="no-referrer">'
        "<style>html,body{margin:0;width:100%;height:100%;overflow:hidden}"
        "iframe{border:0;width:100%;height:100%;display:block}</style></head><body>"
        + frame
        + '<script>window.addEventListener("load",()=>{'
        + f'window.parent.postMessage({event},"*");'
        + "},{once:true});"
        + (
            "window.addEventListener('message',e=>{const d=e.data;"
            "if(e.source!==parent||!d||d.type!=='cygnusx:report-section'||d.reportId!=="
            + json.dumps(str(report_id))
            + "||d.channel!=="
            + json.dumps(channel)
            + "||typeof d.section!=='string'||d.section.length>80)return;"
            "window.frames[0]?.postMessage(d,'*')});"
            + "window.addEventListener('message',e=>{const d=e.data;"
            + "if(e.source!==window.frames[0]||!d||d.type!=='cygnusx:report-selection'||d.reportId!=="
            + json.dumps(str(report_id))
            + "||d.channel!=="
            + json.dumps(channel)
            + "||typeof d.text!=='string'||!d.text||d.text.length>4000"
            + "||typeof d.section!=='string'||d.section.length>80)return;"
            + "parent.postMessage({type:d.type,reportId:d.reportId,channel:d.channel,"
            + "text:d.text,section:d.section,"
            + "x:typeof d.x==='number'?d.x:0,y:typeof d.y==='number'?d.y:0},'*')});"
            if interactive
            else ""
        )
        + "</script></body></html>"
    )
