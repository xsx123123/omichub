# OmicHub BLAST 紧急修复方案 v1.3

> 日期: 2026-07-15  
> 问题: 1) Subject ID 显示为 "CHROMOSOME" 而非 "Chr1"；2) Graphic Summary 无比对条；3) 整体视觉丑  
> 目标: 精准修复，不做多余改动

---

## 一、问题精准诊断 (基于最新截图)

### 问题 1: Subject ID = "CHROMOSOME"，不是 "Chr1"

**截图证据:**
- 表格 Subject ID 列: `CHROMOSOME`
- 表格 Subject Description 列: `dumped from ADB: Feb/3/09 16:9; last updated: 2009-02-02`

**根因:**
你的 FASTA Header 是 `>Chr1 CHROMOSOME dumped...`，`makeblastdb -parse_seqids` 的解析结果是：
- `Hit_accession` = `Chr1`  ← 正确的 ID 在这里
- `Hit_def` = `CHROMOSOME dumped from...`  ← 描述从这里开始，**不含 Chr1**

但你之前的代码按空格切分 `Hit_def`，得到 `hit_id = "CHROMOSOME"`（第一个词）。

**修复:** 后端解析时 **优先用 `Hit_accession`**，只有当它是纯数字序号时才回退到 `Hit_def` 切分。

---

### 问题 2: Graphic Summary 和 Hit 卡片里无比对条 (Bar)

**截图证据:**
- Graphic Summary: 只有一条灰线标尺 (1-36)，下面有 "CHROMOSOME" 标签，但**没有任何彩色 bar**
- Hit 详情卡片 "Query 覆盖位置": 只有标尺线，没有 bar

**根因:**
`BlastGraphicSummary` 和 `BlastAlignmentBar` 的坐标系用错了。

你传的是 `hit_from`/`hit_to` (475-510，Subject 坐标)，但 SVG 的 scale 是按 **Query 长度 (36)** 计算的。`scale(475)` 算出来的 x 坐标远超 SVG 宽度，bar 被画到了视图外面，所以看不到。

**Graphic Summary 的设计意图:** 显示每个 Hit 在 **Query** 上的覆盖位置。x 轴必须是 Query 坐标 (`query_from`/`query_to`)。

**修复:** 把 `hit_from`/`hit_to` 改成 `query_from`/`query_to`。

---

### 问题 3: 视觉丑

**截图证据:**
- "CHROMOSOME" 标签字体太大 (像 h2 标题)
- Graphic Summary 只有一个 Hit 却占了很多纵向空间
- 图例和标签布局松散
- 整体留白过多

**修复:** 压缩布局、缩小字体、精简元素。

---

## 二、后端修复 (仅改 parse_blast_xml)

```python
# backend/utils/blast_xml_parser.py

def parse_blast_xml(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    query_len = int(root.findtext(".//BlastOutput_query-len", "0"))
    program = root.findtext(".//BlastOutput_program", "")
    db_name = root.findtext(".//BlastOutput_db", "")
    query_def = root.findtext(".//BlastOutput_query-def", "")

    hits = []
    for hit_elem in root.findall(".//Hit"):
        hit_def = hit_elem.findtext("Hit_def", "")
        hit_accession = hit_elem.findtext("Hit_accession", "")
        hit_id_raw = hit_elem.findtext("Hit_id", "")  # 可能是 gnl|BL_ORD_ID|0 或 lcl|Chr1

        # ===== 核心修复: 优先取 Hit_accession =====
        if hit_accession and not hit_accession.isdigit():
            hit_id = hit_accession  # Chr1
        elif hit_id_raw and "|" in hit_id_raw:
            # 解析 lcl|Chr1 或 gnl|BL_ORD_ID|0
            parts = hit_id_raw.split("|")
            hit_id = parts[-1] if parts[-1] else hit_id_raw
            if hit_id.isdigit():
                hit_id = hit_def.split(" ")[0] if hit_def else ""
        else:
            hit_id = hit_def.split(" ")[0] if hit_def else ""

        hit_desc = " ".join(hit_def.split(" ")[1:]) if " " in hit_def else ""

        hit_len = int(hit_elem.findtext("Hit_len", "0"))

        hsps = []
        for hsp_elem in hit_elem.findall(".//Hsp"):
            identity = int(hsp_elem.findtext("Hsp_identity", "0"))
            align_length = int(hsp_elem.findtext("Hsp_align-len", "0"))

            hsps.append({
                "hsp_num": int(hsp_elem.findtext("Hsp_num", "0")),
                "bit_score": float(hsp_elem.findtext("Hsp_bit-score", "0")),
                "evalue": float(hsp_elem.findtext("Hsp_evalue", "0")),
                "query_from": int(hsp_elem.findtext("Hsp_query-from", "0")),
                "query_to": int(hsp_elem.findtext("Hsp_query-to", "0")),
                "hit_from": int(hsp_elem.findtext("Hsp_hit-from", "0")),
                "hit_to": int(hsp_elem.findtext("Hsp_hit-to", "0")),
                "identity": identity,
                "align_length": align_length,
                "mismatches": int(hsp_elem.findtext("Hsp_mismatches", "0")),
                "gaps": int(hsp_elem.findtext("Hsp_gaps", "0")),
                "query_seq": hsp_elem.findtext("Hsp_qseq", ""),
                "hit_seq": hsp_elem.findtext("Hsp_hseq", ""),
                "midline": hsp_elem.findtext("Hsp_midline", ""),
            })

        best_hsp = hsps[0] if hsps else None
        identity_percent = round((best_hsp["identity"] / best_hsp["align_length"]) * 100, 2) if best_hsp else 0

        hits.append({
            "hit_num": int(hit_elem.findtext("Hit_num", "0")),
            "hit_id": hit_id,                    # 现在应该是 Chr1
            "hit_def": hit_desc,                # CHROMOSOME dumped...
            "hit_accession": hit_accession,     # Chr1
            "hit_len": hit_len,
            "identity_percent": identity_percent,
            "subject_coverage": round((best_hsp["align_length"] / hit_len) * 100, 2) if best_hsp and hit_len else 0,
            "total_score": sum(h["bit_score"] for h in hsps),
            "best_hsp": best_hsp,
            "hsps": [
                {
                    "query_from": h["query_from"],   # ===== 关键: 传给前端的是 Query 坐标 =====
                    "query_to": h["query_to"],
                    "hit_from": h["hit_from"],
                    "hit_to": h["hit_to"],
                    "identity_percent": round((h["identity"] / h["align_length"]) * 100, 2) if h["align_length"] else 0,
                    "evalue": h["evalue"],
                    "bit_score": h["bit_score"],
                }
                for h in hsps
            ],
        })

    return {
        "program": program,
        "db_name": db_name,
        "query_def": query_def,
        "query_len": query_len,
        "hit_count": len(hits),
        "hits": hits,
    }
```

---

## 三、前端修复 1: Graphic Summary (坐标系修正 + 视觉压缩)

```tsx
// src/components/Blast/BlastGraphicSummary.tsx
import React from "react";
import { Card, Tooltip } from "@arco-design/web-react";

interface HitData {
  hit_num: number;
  hit_id: string;
  hsps: Array<{
    query_from: number;   // ===== 修复: 用 Query 坐标 =====
    query_to: number;
    identity_percent: number;
    evalue: number;
    bit_score: number;
  }>;
}

interface Props {
  queryLen: number;
  hits: HitData[];
}

const BlastGraphicSummary: React.FC<Props> = ({ queryLen, hits }) => {
  const svgWidth = 800;
  const padding = { left: 60, right: 40, top: 6, bottom: 18 };
  const barHeight = 14;
  const trackGap = 4;
  const trackHeight = barHeight + trackGap;
  const svgHeight = padding.top + hits.length * trackHeight + padding.bottom + 16;

  const scale = (pos: number) =>
    padding.left + (pos / queryLen) * (svgWidth - padding.left - padding.right);

  const getColor = (identity: number) => {
    if (identity >= 90) return "#10b981";
    if (identity >= 70) return "#3b82f6";
    if (identity >= 40) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <Card size="small" title="Graphic Summary" style={{ marginBottom: 12 }} bodyStyle={{ padding: "12px 16px" }}>
      <svg width="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ fontFamily: "monospace" }}>
        {/* Query 标尺 */}
        <line
          x1={padding.left}
          y1={padding.top + 8}
          x2={svgWidth - padding.right}
          y2={padding.top + 8}
          stroke="#d1d5db"
          strokeWidth={1.5}
        />
        <text x={padding.left} y={padding.top + 4} textAnchor="middle" fill="#9ca3af" fontSize={9}>1</text>
        <text x={svgWidth - padding.right} y={padding.top + 4} textAnchor="middle" fill="#9ca3af" fontSize={9}>
          {queryLen}
        </text>
        <text x={padding.left - 8} y={padding.top + 12} textAnchor="end" fill="#6b7280" fontSize={10}>Query</text>

        {/* Hit tracks */}
        {hits.map((hit, idx) => {
          const y = padding.top + 18 + idx * trackHeight;
          return (
            <g key={hit.hit_num}>
              {/* Hit ID 标签 (缩小字体) */}
              <text x={padding.left - 6} y={y + barHeight - 2} textAnchor="end" fill="#374151" fontSize={10}>
                {hit.hit_id}
              </text>

              {/* HSP bars (用 query_from/query_to 定位) */}
              {hit.hsps.map((hsp, hspIdx) => {
                const x = scale(hsp.query_from);      // ===== 修复: Query 坐标 =====
                const width = scale(hsp.query_to) - x;  // ===== 修复: Query 坐标 =====
                const color = getColor(hsp.identity_percent);

                return (
                  <Tooltip
                    key={hspIdx}
                    content={
                      <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                        <div><strong>{hit.hit_id}</strong> HSP #{hspIdx + 1}</div>
                        <div>Query: {hsp.query_from}-{hsp.query_to}</div>
                        <div>Identity: {hsp.identity_percent.toFixed(1)}%</div>
                        <div>E: {hsp.evalue.toExponential(2)}</div>
                      </div>
                    }
                  >
                    <rect
                      x={x}
                      y={y}
                      width={Math.max(width, 2)}
                      height={barHeight}
                      rx={3}
                      fill={color}
                      opacity={0.9}
                      style={{ cursor: "pointer" }}
                    />
                  </Tooltip>
                );
              })}
            </g>
          );
        })}

        {/* 紧凑图例 */}
        <g transform={`translate(${padding.left}, ${svgHeight - 14})`}>
          <text x={0} y={0} fontSize={9} fill="#9ca3af">Identity:</text>
          {[
            { c: "#10b981", l: "≥90%" },
            { c: "#3b82f6", l: "≥70%" },
            { c: "#f59e0b", l: "≥40%" },
            { c: "#ef4444", l: "<40%" },
          ].map((item, i) => (
            <g key={i} transform={`translate(${50 + i * 52}, -6)`}>
              <rect width={10} height={10} rx={2} fill={item.c} />
              <text x={14} y={9} fontSize={9} fill="#6b7280">{item.l}</text>
            </g>
          ))}
        </g>
      </svg>
    </Card>
  );
};

export default BlastGraphicSummary;
```

---

## 四、前端修复 2: Hit 详情卡片 (坐标系修正 + 视觉压缩)

```tsx
// src/components/Blast/BlastHitDetailCard.tsx
import React, { useState } from "react";
import { Card, Tag, Descriptions, Button } from "@arco-design/web-react";
import { IconCaretRight, IconCaretDown } from "@arco-design/web-react/icon";
import BlastAlignmentBar from "./BlastAlignmentBar";
import BlastSequenceAlignment from "./BlastSequenceAlignment";

interface HspData {
  query_from: number;
  query_to: number;
  hit_from: number;
  hit_to: number;
  identity: number;
  align_length: number;
  mismatches: number;
  gaps: number;
  evalue: number;
  bit_score: number;
  query_seq: string;
  hit_seq: string;
  midline: string;
}

interface HitData {
  hit_num: number;
  hit_id: string;
  hit_def: string;
  hit_len: number;
  identity_percent: number;
  subject_coverage: number;
  total_score: number;
  best_hsp: HspData;
  hsps: Array<{
    query_from: number;   // ===== 修复: 用 Query 坐标 =====
    query_to: number;
    identity_percent: number;
  }>;
}

interface Props {
  hit: HitData;
  queryLen: number;
}

const BlastHitDetailCard: React.FC<Props> = ({ hit, queryLen }) => {
  const [expanded, setExpanded] = useState(false);

  const getIdentityColor = (v: number) => {
    if (v >= 90) return "green";
    if (v >= 70) return "blue";
    if (v >= 40) return "orange";
    return "red";
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 10 }}
      bodyStyle={{ padding: "12px 16px" }}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
          <strong>Hit #{hit.hit_num}</strong>
          <Tag color="arcoblue" size="small" style={{ fontSize: 12 }}>{hit.hit_id}</Tag>
          <span style={{ color: "var(--color-text-3)", fontSize: 12, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {hit.hit_def}
          </span>
          <Tag color={getIdentityColor(hit.identity_percent)} size="small">
            {hit.identity_percent.toFixed(1)}%
          </Tag>
        </div>
      }
      extra={
        <Button
          type="text"
          size="mini"
          icon={expanded ? <IconCaretDown /> : <IconCaretRight />}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "收起" : "对齐"}
        </Button>
      }
    >
      {/* 紧凑统计信息 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "8px 16px", fontSize: 12, marginBottom: 10 }}>
        <div><span style={{ color: "#6b7280" }}>Subject:</span> {hit.hit_len.toLocaleString()} bp</div>
        <div><span style={{ color: "#6b7280" }}>E-value:</span> {hit.best_hsp.evalue.toExponential(2)}</div>
        <div><span style={{ color: "#6b7280" }}>Bit Score:</span> {hit.best_hsp.bit_score.toFixed(1)}</div>
        <div><span style={{ color: "#6b7280" }}>Align:</span> {hit.best_hsp.align_length} bp</div>
        <div><span style={{ color: "#6b7280" }}>Coverage:</span> {hit.subject_coverage.toFixed(1)}%</div>
        <div><span style={{ color: "#6b7280" }}>Query:</span> {hit.best_hsp.query_from}-{hit.best_hsp.query_to}</div>
        <div><span style={{ color: "#6b7280" }}>Subject:</span> {hit.best_hsp.hit_from}-{hit.best_hsp.hit_to}</div>
        <div><span style={{ color: "#6b7280" }}>Mismatch:</span> {hit.best_hsp.mismatches}</div>
        <div><span style={{ color: "#6b7280" }}>Gaps:</span> {hit.best_hsp.gaps}</div>
        <div><span style={{ color: "#6b7280" }}>Total:</span> {hit.total_score.toFixed(1)}</div>
      </div>

      {/* Query 覆盖条 (用 Query 坐标) */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 4 }}>Query 覆盖位置</div>
        <BlastAlignmentBar
          hitLen={queryLen}      // Query 总长度作为标尺
          hsps={hit.hsps.map(h => ({
            query_from: h.query_from,   // ===== 修复: Query 坐标 =====
            query_to: h.query_to,       // ===== 修复: Query 坐标 =====
            hit_from: h.query_from,     // 传给组件内部统一用 hit_from/hit_to 命名
            hit_to: h.query_to,
            identity_percent: h.identity_percent,
            evalue: hit.best_hsp.evalue,
            bit_score: hit.best_hsp.bit_score,
          }))}
          queryLen={queryLen}
          barHeight={12}
        />
      </div>

      {/* 彩色序列对齐 */}
      {expanded && (
        <BlastSequenceAlignment
          querySeq={hit.best_hsp.query_seq}
          hitSeq={hit.best_hsp.hit_seq}
          midline={hit.best_hsp.midline}
          queryFrom={hit.best_hsp.query_from}
          hitFrom={hit.best_hsp.hit_from}
          lineLength={60}
        />
      )}
    </Card>
  );
};

export default BlastHitDetailCard;
```

---

## 五、前端修复 3: BlastAlignmentBar (坐标系修正)

```tsx
// src/components/Blast/BlastAlignmentBar.tsx
import React from "react";
import { Tooltip } from "@arco-design/web-react";

interface HspData {
  hit_from: number;   // 这里传入的应该是 Query 坐标 (由父组件转换)
  hit_to: number;
  identity_percent: number;
  evalue: number;
  bit_score: number;
}

interface Props {
  hitLen: number;     // 标尺总长度 (Query 长度)
  hsps: HspData[];
  barHeight?: number;
}

const BlastAlignmentBar: React.FC<Props> = ({ hitLen, hsps, barHeight = 14 }) => {
  const svgWidth = 700;
  const padding = { left: 50, right: 30 };
  const svgHeight = barHeight + 16;

  const scale = (pos: number) =>
    padding.left + (pos / hitLen) * (svgWidth - padding.left - padding.right);

  const getColor = (identity: number) => {
    if (identity >= 90) return "#10b981";
    if (identity >= 70) return "#3b82f6";
    if (identity >= 40) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <svg width="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ fontFamily: "monospace", fontSize: 10 }}>
      {/* 标尺 */}
      <line
        x1={padding.left}
        y1={barHeight / 2 + 6}
        x2={svgWidth - padding.right}
        y2={barHeight / 2 + 6}
        stroke="#e5e7eb"
        strokeWidth={1.5}
      />
      <text x={padding.left - 4} y={barHeight / 2 + 10} textAnchor="end" fill="#9ca3af" fontSize={9}>1</text>
      <text x={svgWidth - padding.right + 4} y={barHeight / 2 + 10} textAnchor="start" fill="#9ca3af" fontSize={9}>
        {hitLen.toLocaleString()}
      </text>

      {/* Bars */}
      {hsps.map((hsp, idx) => {
        const x = scale(hsp.hit_from);
        const width = scale(hsp.hit_to) - x;
        const color = getColor(hsp.identity_percent);

        return (
          <Tooltip
            key={idx}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                <div>Range: {hsp.hit_from}-{hsp.hit_to}</div>
                <div>Identity: {hsp.identity_percent.toFixed(1)}%</div>
                <div>E: {hsp.evalue.toExponential(2)}</div>
              </div>
            }
          >
            <rect
              x={x}
              y={6}
              width={Math.max(width, 2)}
              height={barHeight}
              rx={3}
              fill={color}
              opacity={0.9}
              style={{ cursor: "pointer" }}
            />
          </Tooltip>
        );
      })}
    </svg>
  );
};

export default BlastAlignmentBar;
```

---

## 六、修改点总结

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `backend/utils/blast_xml_parser.py` | `hit_id` 优先取 `Hit_accession`，其次解析 `Hit_id`，最后回退 `Hit_def` 切分 | `makeblastdb -parse_seqids` 把 Chr1 放到了 Hit_accession |
| `src/components/Blast/BlastGraphicSummary.tsx` | `scale()` 输入从 `hit_from` 改为 `query_from` | Graphic Summary 显示 Query 坐标 |
| `src/components/Blast/BlastHitDetailCard.tsx` | 传给 `BlastAlignmentBar` 的 `hsps` 使用 `query_from`/`query_to` | 覆盖条显示 Query 坐标 |
| `src/components/Blast/BlastAlignmentBar.tsx` | 无逻辑改动，但确认 `hitLen` 传入 Query 长度 | 标尺与坐标一致 |
| 所有组件 | 字体缩小、padding 压缩、布局紧凑 | 视觉优化 |

---

## 七、验证步骤

1. 重新提交一个 BLAST 任务（或直接用旧任务的 XML 重新解析）
2. 检查返回的 JSON 中 `hits[0].hit_id` 是否为 `Chr1`
3. 检查 `hits[0].hsps[0].query_from` 和 `query_to` 是否为 1-36（Query 坐标）
4. 查看 Graphic Summary 是否出现绿色 bar（在 1-36 范围内）
5. 查看 Hit 详情卡片的 "Query 覆盖位置" 是否出现绿色 bar

如果还有问题，请把后端返回的 JSON（第一个 hit 即可）贴出来，我精确定位。
