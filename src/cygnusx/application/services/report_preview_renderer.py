"""Wrap immutable report bytes in an isolated viewer and a trusted load bridge."""

import html
import json
import re
from uuid import UUID

# Quarto article layouts cap the body-content column at calc(1150px - 2.4rem),
# leaving wide empty margins on desktop screens. The preview is a served view of
# an immutable artifact, so widening is done as a presentation-only override that
# keeps every other track of the grid (TOC, gutters, flexible margins) untouched.
_WIDE_LAYOUT_STYLE = (
    "<style>@media (min-width: 992px){"
    "body .page-columns{grid-template-columns:"
    "[screen-start] 1.2rem [screen-start-inset] 5fr [page-start page-start-inset] 28px "
    "[body-start-outset] 28px [body-start] 1.2rem "
    "[body-content-start] minmax(500px, calc(100vw - 260px)) [body-content-end] 1.2rem "
    "[body-end] 25.2px [body-end-outset] minmax(54px, 104.4px) [page-end-inset] 25.2px "
    "[page-end] 5fr [screen-end-inset] 1.2rem [screen-end] !important}"
    "body:not(.floating):not(.docked) .page-columns.toc-left,"
    "body:not(.floating):not(.docked) .page-columns.toc-left .page-columns{"
    "grid-template-columns:"
    "[screen-start] 1.2rem [screen-start-inset] 5fr [page-start] 28px "
    "[page-start-inset] minmax(0px, 140px) [body-start-outset] 28px [body-start] 1.2rem "
    "[body-content-start] minmax(450px, calc(100vw - 320px)) [body-content-end] 1.2rem "
    "[body-end] 36px [body-end-outset] minmax(0px, 144px) [page-end-inset] 36px "
    "[page-end] 5fr [screen-end-inset] 1.2rem [screen-end] !important}"
    "}</style>"
)


def preview_csp(*, embedded_resources: bool = False) -> str:
    # srcdoc inherits this policy. No remote scripts, requests, forms, popups or
    # same-origin privileges; the nested report has its own sandbox as well.
    # Quarto/DataTables reconstruct serialized callbacks at runtime. Evaluation
    # remains inside the opaque report sandbox, with all network access denied.
    scripts = "'unsafe-inline' 'unsafe-eval' data: blob:" if embedded_resources else "'unsafe-inline'"
    styles = "'unsafe-inline' data: blob:" if embedded_resources else "'unsafe-inline'"
    return (
        "sandbox allow-scripts; default-src 'none'; "
        f"script-src {scripts}; style-src {styles}; "
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
    embedded_resources: bool = False,
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
            + ";window.addEventListener('message',e=>{const d=e.data;"
            + "if(e.source!==parent||e.origin!=='null'||!d||d.type!=='cygnusx:report-section'"
            + "||d.reportId!==id||d.channel!==channel||typeof d.section!=='string'||d.section.length>80)return;"
            + "const h=[...document.querySelectorAll('h1,h2,h3,h4,[role=heading]')]"
            + ".find(x=>(x.textContent||'').trim()===d.section);"
            + "if(h)h.scrollIntoView({behavior:'smooth',block:'start'})});"
            + (
                "document.addEventListener('click',e=>{if(!e.target.closest?.('[data-report-language]'))return;"
                "e.preventDefault();e.stopImmediatePropagation();parent.postMessage({type:'cygnusx:report-language',"
                "reportId:id,channel:channel,language:document.documentElement.lang.startsWith('en')?'zh':'en'},'*')},true);"
                if embedded_resources else ""
            )
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
        if embedded_resources:
            # Quarto expects storage even in offline reports. This is isolated,
            # document-local memory, never platform cookies or persistent storage.
            storage = "<script>(()=>{for(const key of ['localStorage','sessionStorage']){const data=Object.create(null);Object.defineProperty(window,key,{value:{getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=String(v)},removeItem:k=>{delete data[k]},clear:()=>{for(const k of Object.keys(data))delete data[k]},key:i=>Object.keys(data)[i]??null,get length(){return Object.keys(data).length}}})}})();</script>"
            inner_bridge = storage + inner_bridge
        # Register before report scripts run. Appending at the end of complex
        # Quarto HTML can leave the bridge in inert/rewritten document content.
        head = re.search(r"<head(?:\s[^>]*)?>", content, re.IGNORECASE)
        position = head.end() if head else 0
        content = content[:position] + _WIDE_LAYOUT_STYLE + inner_bridge + content[position:]
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
            "if(e.source!==window.frames[0]||!d||d.type!=='cygnusx:report-language'||d.reportId!=="
            + json.dumps(str(report_id)) + "||d.channel!==" + json.dumps(channel)
            + "||!['zh','en'].includes(d.language))return;parent.postMessage(d,'*')});"
            if embedded_resources else ""
        )
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
