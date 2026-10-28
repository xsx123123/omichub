# OmicHub BLAST 结果页面优化方案

> 版本: v1.2  
> 日期: 2026-07-15  
> 目标: 修复 Subject ID 显示、增强比对可视化、消除页面空白

---

## 一、当前问题诊断 (基于最新截图)

### 1.1 Subject 列显示错误

**现状:** 表格 Subject 列显示的是完整描述文本：
```
CHROMOSOME dumped from ADB: Feb/3/09 16:9; last updated: 2009-02-02
```

**期望:** 应该显示序列 ID `Chr1`，描述信息放在 tooltip 或单独列。

**根因:** 
- FASTA Header: `>Chr1 CHROMOSOME dumped from ADB...`
- `makeblastdb -parse_seqids` 将 `Chr1` 解析到了 `Hit_def` 的开头，但 `Hit_accession` 被赋值为序号 `0`
- 前端直接取 `Hit_def` 作为 Subject 名称，导致整段描述挤在一列

---

### 1.2 序列比对详情缺乏可视化

**现状:** 仅显示纯文本对齐：
```
Query  1  TAGTTGTAGGGATGAAGTCTTTCTTCGTTGTTGTTACGCTTGTCATCTCATCTCTCAATGATATGGGATGGTCCTTTAG  79
          |||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
Sbjct  475  TAGTTGTAGGGATGAAGTCTTTCTTCGTTGTTGTTACGCTTGTCATCTCATCTCTCAATGATATGGGATGGTCCTTTAG  553
```

**缺失:**
1. **无颜色编码** — 完全匹配、错配、Gap 都是黑色文字
2. **无比对条 (Alignment Bar)** — 无法直观看到 Query 在 Subject 上的覆盖位置
3. **无序列长度标尺** — 不知道 79bp 的 Query 在 553bp 的 Subject 中占多少比例
4. **无统计摘要** — Identity、E-value、Bit Score 没有在对齐视图旁展示

---

### 1.3 页面下方大量空白

**现状:** 比对结果表格 + 序列比对详情之后，页面下方约 60% 区域空白。

**原因:** 单条结果（1 hit）内容太少，没有充分利用纵向空间。

**优化方向:**
- 增加"Graphic Summary" 可视化区域（比对条分布图）
- 增加"Hit 详情卡片"（每个 Hit 独立卡片，含统计 + 对齐 + 比对条）
- 增加"Query 覆盖度总览"（所有 Hit 的覆盖位置叠加展示）

---

## 二、优化方案总览

```
优化前页面结构:
┌─────────────────────────────────────────────────────────┐
│  右侧信息面板 (序列分析 / 最近任务 / 参数说明)              │
├─────────────────────────────────────────────────────────┤
│  任务状态 + 比对结果表格 (1 行数据)                        │
├─────────────────────────────────────────────────────────┤
│  序列比对详情 (纯文本对齐)                                 │
├─────────────────────────────────────────────────────────┤
│  ❌ 大量空白区域                                          │
└─────────────────────────────────────────────────────────┘

优化后页面结构:
┌─────────────────────────────────────────────────────────┐
│  右侧信息面板 (序列分析 / 最近任务 / 参数说明)              │
├─────────────────────────────────────────────────────────┤
│  任务状态 + 下载按钮 + 统计摘要                            │
├─────────────────────────────────────────────────────────┤
│  【Graphic Summary】Query 覆盖度总览图 (所有 Hit 叠加)      │
├─────────────────────────────────────────────────────────┤
│  比对结果表格 (Subject ID / Desc / Identity / Coverage)    │
├─────────────────────────────────────────────────────────┤
│  【Hit 详情卡片】                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Hit #1  Chr1  [比对条]  Identity: 100%  E: 3.74e-35││
│  │  ┌───────────────────────────────────────────────┐  ││
│  │  │  彩色序列对齐 (绿=匹配 红=错配 灰=Gap)          │  ││
│  │  │  Query  1    TAGTTG...  79                      │  ││
│  │  │              ||||||...                          │  ││
│  │  │  Sbjct  475  TAGTTG...  553                     │  ││
│  │  └───────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────┘│
│  【Hit 详情卡片 #2】...                                   │
├─────────────────────────────────────────────────────────┤
│  参数说明 / 相关工具推荐                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 三、修复 Subject ID 显示

### 3.1 后端 XML 解析增强

```python
# backend/utils/blast_xml_parser.py

def parse_hit_def(hit_def: str) -> tuple[str, str]:
    """
    从 Hit_def 中切分序列 ID 和描述信息。

    FASTA Header 格式: >Chr1 CHROMOSOME dumped from...
    Hit_def 格式:      Chr1 CHROMOSOME dumped from...

    返回: (hit_id, hit_description)
    """
    if not hit_def:
        return "", ""

    parts = hit_def.split(" ", 1)
    hit_id = parts[0].strip()
    hit_desc = parts[1].strip() if len(parts) > 1 else ""

    # 如果 hit_id 是纯数字（makeblastdb 的序号），尝试从 def 中提取
    if hit_id.isdigit() and hit_desc:
        # 有些数据库格式是 "0 Chr1 desc"，再切一次
        sub_parts = hit_desc.split(" ", 1)
        if sub_parts[0] and not sub_parts[0].isdigit():
            hit_id = sub_parts[0]
            hit_desc = sub_parts[1] if len(sub_parts) > 1 else ""

    return hit_id, hit_desc


def parse_blast_xml(xml_path: str) -> dict:
    """增强版 XML 解析"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    query_len = int(root.findtext(".//BlastOutput_query-len", "0"))
    program = root.findtext(".//BlastOutput_program", "")
    db_name = root.findtext(".//BlastOutput_db", "")
    query_def = root.findtext(".//BlastOutput_query-def", "")

    hits = []
    for hit_elem in root.findall(".//Hit"):
        hit_def = hit_elem.findtext("Hit_def", "")
        hit_id, hit_desc = parse_hit_def(hit_def)

        # 如果 accession 是数字序号，用 hit_id 覆盖
        hit_accession = hit_elem.findtext("Hit_accession", "")
        if hit_accession.isdigit() and hit_id:
            hit_accession = hit_id

        hit_len = int(hit_elem.findtext("Hit_len", "0"))

        hsps = []
        for hsp_elem in hit_elem.findall(".//Hsp"):
            hsps.append({
                "hsp_num": int(hsp_elem.findtext("Hsp_num", "0")),
                "bit_score": float(hsp_elem.findtext("Hsp_bit-score", "0")),
                "evalue": float(hsp_elem.findtext("Hsp_evalue", "0")),
                "query_from": int(hsp_elem.findtext("Hsp_query-from", "0")),
                "query_to": int(hsp_elem.findtext("Hsp_query-to", "0")),
                "hit_from": int(hsp_elem.findtext("Hsp_hit-from", "0")),
                "hit_to": int(hsp_elem.findtext("Hsp_hit-to", "0")),
                "identity": int(hsp_elem.findtext("Hsp_identity", "0")),
                "align_length": int(hsp_elem.findtext("Hsp_align-len", "0")),
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
            "hit_id": hit_id,                    # Chr1
            "hit_def": hit_desc,                # CHROMOSOME dumped...
            "hit_accession": hit_accession,     # Chr1
            "hit_len": hit_len,                 # 553
            "identity_percent": identity_percent,
            "subject_coverage": round((best_hsp["align_length"] / hit_len) * 100, 2) if best_hsp and hit_len else 0,
            "total_score": sum(h["bit_score"] for h in hsps),
            "best_hsp": best_hsp,
            "hsps": [
                {
                    "query_from": h["query_from"],
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

### 3.2 前端表格列调整

```tsx
// src/pages/Blast/BlastResultPage.tsx

const columns = [
  {
    title: "#",
    dataIndex: "hit_num",
    width: 50,
    align: "center" as const,
    render: (v: number) => <strong>{v}</strong>,
  },
  {
    title: "Subject ID",
    dataIndex: "hit_id",
    width: 100,
    render: (v: string, record: any) => (
      <Tooltip content={record.hit_def || "无描述"}>
        <span style={{ 
          fontFamily: "monospace", 
          fontWeight: 600,
          fontSize: 13,
          color: "var(--color-text-1)"
        }}>
          {v}
        </span>
      </Tooltip>
    ),
  },
  {
    title: "Subject Description",
    dataIndex: "hit_def",
    width: 280,
    ellipsis: { showTitle: true },
    render: (v: string) => (
      <span style={{ fontSize: 12, color: "var(--color-text-3)" }}>
        {v || "-"}
      </span>
    ),
  },
  {
    title: "Length",
    dataIndex: "hit_len",
    width: 80,
    align: "right" as const,
    render: (v: number) => `${v.toLocaleString()} bp`,
  },
  {
    title: "Identity %",
    dataIndex: "identity_percent",
    width: 90,
    align: "center" as const,
    sorter: (a: any, b: any) => a.identity_percent - b.identity_percent,
    render: (v: number) => {
      let color = "red";
      if (v >= 90) color = "green";
      else if (v >= 70) color = "blue";
      else if (v >= 40) color = "orange";
      return <Tag color={color} size="small">{v.toFixed(1)}%</Tag>;
    },
  },
  {
    title: "E-value",
    dataIndex: ["best_hsp", "evalue"],
    width: 110,
    sorter: (a: any, b: any) => a.best_hsp.evalue - b.best_hsp.evalue,
    render: (v: number) => {
      if (v < 1e-100) return <Tag color="red" size="small">{v.toExponential(1)}</Tag>;
      return <span style={{ fontFamily: "monospace", fontSize: 12 }}>{v.toExponential(2)}</span>;
    },
  },
  {
    title: "Bit Score",
    dataIndex: ["best_hsp", "bit_score"],
    width: 90,
    align: "right" as const,
    sorter: (a: any, b: any) => a.best_hsp.bit_score - b.best_hsp.bit_score,
    render: (v: number) => <span style={{ fontFamily: "monospace" }}>{v.toFixed(1)}</span>,
  },
  {
    title: "Align Len",
    dataIndex: ["best_hsp", "align_length"],
    width: 90,
    align: "right" as const,
    render: (v: number) => `${v} bp`,
  },
  {
    title: "Query Range",
    dataIndex: "best_hsp",
    width: 100,
    align: "center" as const,
    render: (hsp: any) => (
      <span style={{ fontFamily: "monospace", fontSize: 12 }}>
        {hsp.query_from}-{hsp.query_to}
      </span>
    ),
  },
  {
    title: "Subject Range",
    dataIndex: "best_hsp",
    width: 100,
    align: "center" as const,
    render: (hsp: any) => (
      <span style={{ fontFamily: "monospace", fontSize: 12 }}>
        {hsp.hit_from}-{hsp.hit_to}
      </span>
    ),
  },
  {
    title: "Coverage",
    dataIndex: "subject_coverage",
    width: 120,
    sorter: (a: any, b: any) => a.subject_coverage - b.subject_coverage,
    render: (v: number) => (
      <Progress
        percent={v}
        size="small"
        status={v > 80 ? "success" : v > 50 ? "normal" : "warning"}
        format={(percent) => `${percent?.toFixed(1)}%`}
      />
    ),
  },
];
```

---

## 四、Graphic Summary 可视化 (Query 覆盖度总览)

### 4.1 组件设计

```tsx
// src/components/Blast/BlastGraphicSummary.tsx
import React from "react";
import { Card, Tooltip } from "@arco-design/web-react";

interface HitData {
  hit_num: number;
  hit_id: string;
  hit_len: number;
  hsps: Array<{
    hit_from: number;
    hit_to: number;
    identity_percent: number;
    evalue: number;
    bit_score: number;
  }>;
}

interface BlastGraphicSummaryProps {
  queryLen: number;
  hits: HitData[];
  barHeight?: number;
}

const BlastGraphicSummary: React.FC<BlastGraphicSummaryProps> = ({
  queryLen,
  hits,
  barHeight = 20,
}) => {
  const svgWidth = 800;
  const padding = { left: 80, right: 20, top: 10, bottom: 10 };
  const trackHeight = barHeight + 16;
  const svgHeight = padding.top + hits.length * trackHeight + padding.bottom;

  const scale = (pos: number) =>
    padding.left + (pos / queryLen) * (svgWidth - padding.left - padding.right);

  const getColor = (identity: number) => {
    if (identity >= 90) return "#10b981";
    if (identity >= 70) return "#3b82f6";
    if (identity >= 40) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <Card size="small" title="Graphic Summary" style={{ marginBottom: 16 }}>
      <svg width="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ fontFamily: "monospace", fontSize: 11 }}>
        {/* Query 标尺 */}
        <line
          x1={padding.left}
          y1={padding.top + 5}
          x2={svgWidth - padding.right}
          y2={padding.top + 5}
          stroke="#e5e7eb"
          strokeWidth={2}
        />
        <text x={padding.left - 8} y={padding.top + 9} textAnchor="end" fill="#6b7280" fontSize={10}>
          Query
        </text>
        <text x={padding.left} y={padding.top - 2} textAnchor="middle" fill="#9ca3af" fontSize={9}>
          1
        </text>
        <text x={svgWidth - padding.right} y={padding.top - 2} textAnchor="middle" fill="#9ca3af" fontSize={9}>
          {queryLen}
        </text>

        {/* 每个 Hit 的覆盖条 */}
        {hits.map((hit, idx) => {
          const y = padding.top + 20 + idx * trackHeight;

          return (
            <g key={hit.hit_num}>
              {/* Hit 标签 */}
              <text x={padding.left - 8} y={y + barHeight / 2 + 4} textAnchor="end" fill="#374151" fontSize={11}>
                {hit.hit_id}
              </text>

              {/* HSP 覆盖条 */}
              {hit.hsps.map((hsp, hspIdx) => {
                const x = scale(hsp.hit_from);
                const width = scale(hsp.hit_to) - x;
                const color = getColor(hsp.identity_percent);

                return (
                  <Tooltip
                    key={hspIdx}
                    content={
                      <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                        <div><strong>{hit.hit_id}</strong> HSP #{hspIdx + 1}</div>
                        <div>Range: {hsp.hit_from}-{hsp.hit_to}</div>
                        <div>Identity: {hsp.identity_percent.toFixed(1)}%</div>
                        <div>E-value: {hsp.evalue.toExponential(2)}</div>
                        <div>Bit Score: {hsp.bit_score}</div>
                      </div>
                    }
                  >
                    <rect
                      x={x}
                      y={y}
                      width={Math.max(width, 3)}
                      height={barHeight}
                      rx={3}
                      fill={color}
                      opacity={0.85}
                      style={{ cursor: "pointer" }}
                    />
                  </Tooltip>
                );
              })}

              {/* 标尺线 */}
              <line
                x1={padding.left}
                y1={y + barHeight + 6}
                x2={svgWidth - padding.right}
                y2={y + barHeight + 6}
                stroke="#f3f4f6"
                strokeWidth={1}
              />
            </g>
          );
        })}

        {/* 图例 */}
        <g transform={`translate(${padding.left}, ${svgHeight - 14})`}>
          <text x={0} y={0} fontSize={10} fill="#6b7280">图例:</text>
          {[
            { color: "#10b981", label: ">=90%" },
            { color: "#3b82f6", label: ">=70%" },
            { color: "#f59e0b", label: ">=40%" },
            { color: "#ef4444", label: "<40%" },
          ].map((item, i) => (
            <g key={i} transform={`translate(${40 + i * 60}, -8)`}>
              <rect width={12} height={12} rx={2} fill={item.color} opacity={0.85} />
              <text x={16} y={10} fontSize={9} fill="#6b7280">{item.label}</text>
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

## 五、Hit 详情卡片 (彩色序列对齐 + 比对条)

### 5.1 组件设计

```tsx
// src/components/Blast/BlastHitDetailCard.tsx
import React, { useState } from "react";
import { Card, Tag, Descriptions, Button, Collapse } from "@arco-design/web-react";
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
    hit_from: number;
    hit_to: number;
    identity_percent: number;
  }>;
}

interface BlastHitDetailCardProps {
  hit: HitData;
  queryLen: number;
  defaultExpanded?: boolean;
}

const BlastHitDetailCard: React.FC<BlastHitDetailCardProps> = ({
  hit,
  queryLen,
  defaultExpanded = false,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const getIdentityColor = (v: number) => {
    if (v >= 90) return "green";
    if (v >= 70) return "blue";
    if (v >= 40) return "orange";
    return "red";
  };

  return (
    <Card
      size="small"
      style={{ marginBottom: 12 }}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontWeight: 600 }}>Hit #{hit.hit_num}</span>
          <Tag color="arcoblue" size="small">{hit.hit_id}</Tag>
          <span style={{ fontSize: 12, color: "var(--color-text-3)", flex: 1 }}>
            {hit.hit_def}
          </span>
          <Tag color={getIdentityColor(hit.identity_percent)} size="small">
            Identity: {hit.identity_percent.toFixed(1)}%
          </Tag>
        </div>
      }
      extra={
        <Button
          type="text"
          size="small"
          icon={expanded ? <IconCaretDown /> : <IconCaretRight />}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "收起" : "展开对齐"}
        </Button>
      }
    >
      {/* 统计信息 */}
      <Descriptions
        layout="inline-horizontal"
        size="mini"
        column={6}
        data={[
          { label: "Subject Length", value: `${hit.hit_len.toLocaleString()} bp` },
          { label: "E-value", value: hit.best_hsp.evalue.toExponential(2) },
          { label: "Bit Score", value: hit.best_hsp.bit_score.toFixed(1) },
          { label: "Align Length", value: `${hit.best_hsp.align_length} bp` },
          { label: "Mismatches", value: hit.best_hsp.mismatches },
          { label: "Gaps", value: hit.best_hsp.gaps },
          { label: "Query Range", value: `${hit.best_hsp.query_from}-${hit.best_hsp.query_to}` },
          { label: "Subject Range", value: `${hit.best_hsp.hit_from}-${hit.best_hsp.hit_to}` },
          { label: "Subject Coverage", value: `${hit.subject_coverage.toFixed(1)}%` },
          { label: "Total Score", value: hit.total_score.toFixed(1) },
        ]}
        style={{ marginBottom: 12 }}
      />

      {/* 比对条 (显示该 Hit 在 Query 上的覆盖位置) */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: "var(--color-text-3)", marginBottom: 4 }}>
          Query 覆盖位置
        </div>
        <BlastAlignmentBar
          hitLen={queryLen}
          hsps={hit.hsps.map(h => ({
            query_from: h.hit_from,
            query_to: h.hit_to,
            hit_from: h.hit_from,
            hit_to: h.hit_to,
            identity_percent: h.identity_percent,
            evalue: hit.best_hsp.evalue,
            bit_score: hit.best_hsp.bit_score,
          }))}
          queryLen={queryLen}
          barHeight={16}
        />
      </div>

      {/* 彩色序列对齐 (展开时显示) */}
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

## 六、彩色序列对齐组件 (优化版)

```tsx
// src/components/Blast/BlastSequenceAlignment.tsx
import React from "react";
import { Card } from "@arco-design/web-react";

interface SequenceAlignmentProps {
  querySeq: string;
  hitSeq: string;
  midline: string;
  queryFrom: number;
  hitFrom: number;
  lineLength?: number;
}

const BlastSequenceAlignment: React.FC<SequenceAlignmentProps> = ({
  querySeq,
  hitSeq,
  midline,
  queryFrom,
  hitFrom,
  lineLength = 60,
}) => {
  const lines: Array<{
    q: string;
    m: string;
    s: string;
    qStart: number;
    sStart: number;
  }> = [];

  for (let i = 0; i < querySeq.length; i += lineLength) {
    const qLine = querySeq.slice(i, i + lineLength);
    const mLine = midline.slice(i, i + lineLength);
    const sLine = hitSeq.slice(i, i + lineLength);

    const qGapsBefore = (querySeq.slice(0, i).match(/-/g) || []).length;
    const sGapsBefore = (hitSeq.slice(0, i).match(/-/g) || []).length;

    lines.push({
      q: qLine,
      m: mLine,
      s: sLine,
      qStart: queryFrom + i - qGapsBefore,
      sStart: hitFrom + i - sGapsBefore,
    });
  }

  const getBaseStyle = (qBase: string, mChar: string) => {
    if (mChar === "|") {
      return { color: "#059669", fontWeight: 700, backgroundColor: "#d1fae5" };
    }
    if (mChar === "+") {
      return { color: "#d97706", fontWeight: 600, backgroundColor: "#fef3c7" };
    }
    if (qBase === "-") {
      return { color: "#9ca3af", fontWeight: 400 };
    }
    return { color: "#dc2626", fontWeight: 600, backgroundColor: "#fee2e2" };
  };

  return (
    <Card size="small" title="序列比对详情" style={{ marginTop: 8, fontFamily: "monospace" }}>
      <div style={{ overflowX: "auto" }}>
        {lines.map((line, idx) => (
          <div key={idx} style={{ marginBottom: 8, lineHeight: 1.8 }}>
            {/* Query 行 */}
            <div style={{ display: "flex", gap: 8, fontSize: 13 }}>
              <span style={{ width: 70, textAlign: "right", color: "#6b7280", fontSize: 11, flexShrink: 0 }}>
                Query {line.qStart}
              </span>
              <span>
                {line.q.split("").map((base, i) => (
                  <span key={i} style={{ ...getBaseStyle(base, line.m[i]), padding: "0 1px" }}>
                    {base}
                  </span>
                ))}
              </span>
              <span style={{ color: "#6b7280", fontSize: 11, marginLeft: 8 }}>
                {line.qStart + line.q.replace(/-/g, "").length - 1}
              </span>
            </div>

            {/* Midline */}
            <div style={{ display: "flex", gap: 8, marginLeft: 78 }}>
              <span style={{ color: "#9ca3af", letterSpacing: 1, fontSize: 13 }}>
                {line.m}
              </span>
            </div>

            {/* Subject 行 */}
            <div style={{ display: "flex", gap: 8, fontSize: 13 }}>
              <span style={{ width: 70, textAlign: "right", color: "#6b7280", fontSize: 11, flexShrink: 0 }}>
                Sbjct {line.sStart}
              </span>
              <span>
                {line.s.split("").map((base, i) => (
                  <span key={i} style={{ ...getBaseStyle(base, line.m[i]), padding: "0 1px" }}>
                    {base}
                  </span>
                ))}
              </span>
              <span style={{ color: "#6b7280", fontSize: 11, marginLeft: 8 }}>
                {line.sStart + line.s.replace(/-/g, "").length - 1}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* 图例 */}
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid #e5e7eb", fontSize: 12, display: "flex", gap: 20 }}>
        <span><span style={{ color: "#059669", fontWeight: 700 }}>AAA</span> 完全匹配 (|)</span>
        <span><span style={{ color: "#d97706", fontWeight: 600 }}>AAA</span> 相似匹配 (+)</span>
        <span><span style={{ color: "#dc2626", fontWeight: 600 }}>AAA</span> 错配</span>
        <span><span style={{ color: "#9ca3af" }}>---</span> Gap</span>
      </div>
    </Card>
  );
};

export default BlastSequenceAlignment;
```

---

## 七、比对条组件 (BlastAlignmentBar)

```tsx
// src/components/Blast/BlastAlignmentBar.tsx
import React from "react";
import { Tooltip } from "@arco-design/web-react";

interface HspData {
  query_from: number;
  query_to: number;
  hit_from: number;
  hit_to: number;
  identity_percent: number;
  evalue: number;
  bit_score: number;
}

interface BlastAlignmentBarProps {
  hitLen: number;
  hsps: HspData[];
  queryLen: number;
  barHeight?: number;
  showRuler?: boolean;
}

const BlastAlignmentBar: React.FC<BlastAlignmentBarProps> = ({
  hitLen,
  hsps,
  barHeight = 20,
  showRuler = true,
}) => {
  const svgWidth = 700;
  const padding = { left: showRuler ? 60 : 10, right: 20 };
  const svgHeight = barHeight + (showRuler ? 20 : 0);

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
      {/* 标尺线 */}
      {showRuler && (
        <>
          <line
            x1={padding.left}
            y1={barHeight / 2 + 8}
            x2={svgWidth - padding.right}
            y2={barHeight / 2 + 8}
            stroke="#e5e7eb"
            strokeWidth={2}
          />
          <text x={padding.left - 5} y={barHeight / 2 + 12} textAnchor="end" fill="#9ca3af">1</text>
          <text x={svgWidth - padding.right + 5} y={barHeight / 2 + 12} textAnchor="start" fill="#9ca3af">
            {hitLen.toLocaleString()}
          </text>
        </>
      )}

      {/* HSP 覆盖条 */}
      {hsps.map((hsp, idx) => {
        const x = scale(hsp.hit_from);
        const width = scale(hsp.hit_to) - x;
        const color = getColor(hsp.identity_percent);

        return (
          <Tooltip
            key={idx}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                <div><strong>Range:</strong> {hsp.hit_from}-{hsp.hit_to}</div>
                <div><strong>Identity:</strong> {hsp.identity_percent.toFixed(1)}%</div>
                <div><strong>E-value:</strong> {hsp.evalue.toExponential(2)}</div>
                <div><strong>Bit Score:</strong> {hsp.bit_score}</div>
              </div>
            }
          >
            <rect
              x={x}
              y={showRuler ? 8 : 0}
              width={Math.max(width, 3)}
              height={barHeight}
              rx={4}
              fill={color}
              opacity={0.85}
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

## 八、结果页面整合 (BlastResultPage.tsx)

```tsx
// src/pages/Blast/BlastResultPage.tsx
import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Card, Spin, Table, Message, Button, Space, Tag, Statistic, Divider } from "@arco-design/web-react";
import { IconDownload, IconArrowLeft } from "@arco-design/web-react/icon";
import { useNavigate } from "react-router-dom";
import { downloadWithAuth } from "@/utils/downloadFile";
import { useAuth } from "@/context/AuthContext";

import BlastGraphicSummary from "@/components/Blast/BlastGraphicSummary";
import BlastHitDetailCard from "@/components/Blast/BlastHitDetailCard";

const BlastResultPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [resultData, setResultData] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/blast/results/${taskId}?format=json`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(data => {
        setResultData(data);
        setLoading(false);
      })
      .catch(() => {
        Message.error("加载结果失败");
        setLoading(false);
      });
  }, [taskId, token]);

  const handleDownload = async (format: "xml" | "json" | "text") => {
    const url = `/api/blast/results/${taskId}?format=${format}`;
    const filename = `blast_result_${taskId}.${format}`;
    try {
      await downloadWithAuth(url, filename, token);
      Message.success("下载成功");
    } catch (error: any) {
      Message.error(error.message || "下载失败");
    }
  };

  if (loading) {
    return <Spin size={40} style={{ display: "block", margin: "100px auto" }} />;
  }

  const { hit_count, query_len, hits, db_name, program } = resultData || {};

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      {/* 顶部导航 + 标题 */}
      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 16 }}>
        <Button icon={<IconArrowLeft />} onClick={() => navigate("/tools/blast")}>
          返回
        </Button>
        <h2 style={{ margin: 0, fontSize: 18 }}>
          BLAST 结果: {resultData?.query_def || taskId}
        </h2>
      </div>

      {/* 统计摘要 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space size="large">
          <Statistic title="数据库" value={db_name} />
          <Statistic title="算法" value={program?.toUpperCase()} />
          <Statistic title="Query 长度" value={`${query_len} bp`} />
          <Statistic title="命中数" value={hit_count} />
          <Statistic 
            title="最佳 E-value" 
            value={hits?.[0]?.best_hsp?.evalue?.toExponential(2) || "-"} 
          />
          <Statistic 
            title="最佳 Identity" 
            value={`${hits?.[0]?.identity_percent?.toFixed(1) || 0}%`} 
          />
        </Space>

        <Divider style={{ margin: "12px 0" }} />

        <Space>
          <Button size="small" icon={<IconDownload />} onClick={() => handleDownload("xml")}>
            XML
          </Button>
          <Button size="small" icon={<IconDownload />} onClick={() => handleDownload("json")}>
            JSON
          </Button>
          <Button size="small" icon={<IconDownload />} onClick={() => handleDownload("text")}>
            Text
          </Button>
        </Space>
      </Card>

      {/* Graphic Summary (Query 覆盖度总览) */}
      {hit_count > 0 && (
        <BlastGraphicSummary queryLen={query_len} hits={hits} />
      )}

      {/* 比对结果表格 */}
      <Card size="small" title="比对结果" style={{ marginBottom: 16 }}>
        <Table
          columns={columns}
          data={hits || []}
          rowKey="hit_num"
          pagination={{ pageSize: 20, size: "small" }}
          scroll={{ x: 1200 }}
          size="small"
        />
      </Card>

      {/* Hit 详情卡片列表 */}
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12, color: "var(--color-text-2)" }}>
          序列比对详情 ({hit_count} hits)
        </h3>
        {hits?.map((hit: any) => (
          <BlastHitDetailCard
            key={hit.hit_num}
            hit={hit}
            queryLen={query_len}
            defaultExpanded={hit.hit_num === 1} // 默认展开第一个
          />
        ))}
      </div>
    </div>
  );
};

export default BlastResultPage;
```

---

## 九、后端 Celery 任务修改

```python
# backend/tasks/blast_search.py

def parse_blast_xml(xml_path: str) -> dict:
    """增强版 XML 解析，提取完整 Hit 元数据。"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    query_len = int(root.findtext(".//BlastOutput_query-len", "0"))
    program = root.findtext(".//BlastOutput_program", "")
    db_name = root.findtext(".//BlastOutput_db", "")
    query_def = root.findtext(".//BlastOutput_query-def", "")

    hits = []
    for hit_elem in root.findall(".//Hit"):
        hit_def = hit_elem.findtext("Hit_def", "")

        # 切分 ID 和 Description
        hit_parts = hit_def.split(" ", 1)
        hit_id = hit_parts[0].strip() if hit_parts else ""
        hit_desc = hit_parts[1].strip() if len(hit_parts) > 1 else ""

        # 如果 accession 是数字，用 hit_id 覆盖
        hit_accession = hit_elem.findtext("Hit_accession", "")
        if hit_accession.isdigit() and hit_id:
            hit_accession = hit_id

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
            "hit_id": hit_id,
            "hit_def": hit_desc,
            "hit_accession": hit_accession,
            "hit_len": hit_len,
            "identity_percent": identity_percent,
            "subject_coverage": round((best_hsp["align_length"] / hit_len) * 100, 2) if best_hsp and hit_len else 0,
            "total_score": sum(h["bit_score"] for h in hsps),
            "best_hsp": best_hsp,
            "hsps": [
                {
                    "query_from": h["query_from"],
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

## 十、验收标准

### 10.1 Subject ID 显示
- [ ] 表格 Subject ID 列显示 `Chr1` 而非整段描述
- [ ] 描述文本显示在 Description 列，过长时 ellipsis
- [ ] Hover Subject ID 显示完整描述 tooltip

### 10.2 Graphic Summary
- [ ] 页面顶部显示 Query 覆盖度总览图
- [ ] 每个 Hit 一条 track，显示在 Query 上的覆盖位置
- [ ] 覆盖条颜色按 Identity 编码：绿(>=90%) / 蓝(>=70%) / 橙(>=40%) / 红(<40%)
- [ ] Hover 覆盖条显示详细统计
- [ ] 底部显示图例

### 10.3 Hit 详情卡片
- [ ] 每个 Hit 一个独立卡片，包含统计信息、比对条、彩色对齐
- [ ] 卡片默认折叠，点击展开显示彩色序列对齐
- [ ] 比对条显示该 Hit 在 Query 上的覆盖位置
- [ ] 序列对齐中完全匹配显示绿色背景+深绿字，错配显示红色背景+深红字，Gap 灰色
- [ ] 显示 Query/Sbjct 位置标尺

### 10.4 页面布局
- [ ] 单条结果时页面无大片空白（Graphic Summary + 表格 + 详情卡片填满）
- [ ] 多条结果时支持滚动查看所有 Hit 卡片
- [ ] 页面最大宽度 1200px，居中显示

---

## 十一、修改文件清单

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `src/utils/downloadFile.ts` | 新增 | 带认证下载工具 |
| `src/components/Blast/BlastGraphicSummary.tsx` | 新增 | Query 覆盖度总览图 |
| `src/components/Blast/BlastHitDetailCard.tsx` | 新增 | Hit 详情卡片 |
| `src/components/Blast/BlastAlignmentBar.tsx` | 新增 | SVG 比对条 |
| `src/components/Blast/BlastSequenceAlignment.tsx` | 新增 | 彩色序列对齐 |
| `src/pages/Blast/BlastResultPage.tsx` | 重写 | 整合所有新组件 |
| `backend/utils/blast_xml_parser.py` | 修改 | 切分 hit_id / hit_def |
| `backend/tasks/blast_search.py` | 修改 | 生成含完整信息的 JSON 缓存 |
| `backend/routes/blast.py` | 修改 | 下载 API 支持认证 |

---

## 十二、颜色编码规范

| Identity | 颜色 | Hex | 背景 | 含义 |
|----------|------|-----|------|------|
| >= 90% | 深绿 | #059669 | #d1fae5 | 高度相似 |
| >= 70% | 蓝色 | #3b82f6 | #dbeafe | 较相似 |
| >= 40% | 橙色 | #d97706 | #fef3c7 | 中等相似 |
| < 40% | 红色 | #dc2626 | #fee2e2 | 低相似 |
| Gap | 灰色 | #9ca3af | - | 空位 |

---

## 十三、版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|----------|------|
| v1.2 | 2026-07-15 | 基于截图诊断，新增 Graphic Summary 和 Hit 详情卡片 | Kimi |
