# OmicHub BLAST 模块问题诊断与优化方案

> 版本: v1.1  
> 日期: 2026-07-15  
> 问题来源: 用户实际使用反馈  
> 目标: 修复下载认证、补充 Subject 信息、增加比对可视化

---

## 一、问题诊断 (Problem Diagnosis)

### 问题 1: 下载结果提示 {"detail":"未提供认证令牌"}

**根因分析:**

前端下载按钮使用了 `window.open(url)` 或 `<a href="url" download>` 的方式直接打开 API 链接：

```tsx
// 错误实现
<Button onClick={() => window.open(`/api/blast/results/${taskId}?format=xml`)}>
  下载 XML
</Button>
```

浏览器通过新窗口/标签页发起请求时，**不会自动携带自定义 HTTP Header**（如 `Authorization: Bearer <token>`）。而你的 FastAPI 后端使用 JWT Bearer Token 认证，导致请求被 401 拦截。

**影响范围:** XML、JSON、Text 三种格式的下载按钮均受影响。

---

### 问题 2: 结果表格缺少 Subject 序列的详细信息

**根因分析:**

当前 XML 解析逻辑只提取了基础字段（Identity、E-value、Bit Score 等），但**遗漏了 BLAST XML 中的关键 Hit 元数据**：

```xml
<!-- BLAST XML 中的 Hit 结构 -->
<Hit>
  <Hit_num>1</Hit_num>
  <Hit_id>gnl|BL_ORD_ID|0</Hit_id>
  <Hit_def>CHROMOSOME dumped from ADB: Feb/3/09 16:9; last updated: 2009-02-02</Hit_def>
  <Hit_accession>0</Hit_accession>
  <Hit_len>553</Hit_len>
  <Hsp>
    <Hsp_num>1</Hsp_num>
    <Hsp_bit-score>147.0</Hsp_bit-score>
    <Hsp_evalue>3.74e-35</Hsp_evalue>
    <Hsp_query-from>1</Hsp_query-from>
    <Hsp_query-to>79</Hsp_query-to>
    <Hsp_hit-from>475</Hsp_hit-from>
    <Hsp_hit-to>553</Hsp_hit-to>
    <Hsp_identity>79</Hsp_identity>
    <Hsp_align-len>79</Hsp_align-len>
    <Hsp_qseq>TAGTTGTAGGGATGAAGTCTTTCTTCGTTGTTGTTACGCTTGTCATCTCATCTCTCAATGATATGGGATGGTCCTTTAG</Hsp_qseq>
    <Hsp_hseq>TAGTTGTAGGGATGAAGTCTTTCTTCGTTGTTGTTACGCTTGTCATCTCATCTCTCAATGATATGGGATGGTCCTTTAG</Hsp_hseq>
    <Hsp_midline>|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||</Hsp_midline>
  </Hsp>
</Hit>
```

当前解析只取了 `Hsp_*` 字段，**没有提取 `Hit_def`（序列描述）、`Hit_accession`（序列 ID）、`Hit_len`（序列总长度）**。导致用户不知道比对到了哪个基因/染色体。

**用户期望的表格字段:**
- Subject ID / Accession (序列唯一标识)
- Subject Description (序列功能描述)
- Subject Length (序列总长度)
- Query Coverage (查询覆盖度)
- Subject Coverage (目标覆盖度)

---

### 问题 3: 比对结果无可视化，仅有纯文本对齐

**根因分析:**

当前结果展示只有 `Hsp_qseq` / `Hsp_midline` / `Hsp_hseq` 的文本对齐，缺乏：
1. **比对条 (Alignment Bar)**：直观显示 Query 在 Subject 上的覆盖位置和匹配质量
2. **颜色编码**：根据 Identity 百分比用不同颜色区分匹配质量
3. **序列长度标尺**：显示 Subject 总长度和比对位置的比例关系

**参考标准:** NCBI BLAST 结果页面的 Graphic Summary 和 Alignments 视图。

---

## 二、优化方案 (Optimization Plan)

### 2.1 整体架构调整

```
前端 (React + Arco)
  下载按钮      结果表格      比对可视化
  (Blob下载)    (新增字段)    (SVG Bar)
       |            |            |
       v            v            v
  BlastResultPage.tsx (重构)
    - 下载: fetch + Blob + URL.createObjectURL
    - 表格: 新增 Subject ID/Desc/Length/Coverage
    - 可视化: BlastAlignmentBar (SVG)
              |
              v POST /api/blast/results/{id}?format=xxx
后端 (FastAPI)
  认证中间件    XML解析增强   多格式响应
  (Cookie备选)  (Hit元数据)   (XML/JSON/Text)
```

---

## 三、问题 1 修复: 下载认证

### 3.1 方案对比

| 方案 | 实现复杂度 | 安全性 | 用户体验 | 推荐度 |
|------|-----------|--------|----------|--------|
| **A. fetch + Blob 下载** | 低 | 高 | 好 | 推荐 |
| B. URL Query Token | 低 | 中 | 好 | 备选 |
| C. Cookie 认证 | 中 | 高 | 好 | 推荐 |
| D. 后端生成预签名 URL | 高 | 高 | 最好 | 远期 |

**推荐方案 A + C 组合**：前端用 fetch 携带 Header 下载，后端同时支持 Cookie 作为 fallback。

### 3.2 前端实现 (fetch + Blob)

```tsx
// src/utils/downloadFile.ts
/**
 * 带认证的通用文件下载
 * @param url API 下载地址
 * @param filename 保存文件名
 * @param token JWT Token
 */
export async function downloadWithAuth(
  url: string,
  filename: string,
  token: string
): Promise<void> {
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `下载失败: ${response.status}`);
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    throw error;
  }
}
```

```tsx
// src/pages/Blast/BlastResultPage.tsx
import { downloadWithAuth } from "@/utils/downloadFile";
import { useAuth } from "@/context/AuthContext";

const BlastResultPage: React.FC = () => {
  const { token } = useAuth();
  const { taskId } = useParams();

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

  return (
    <Card
      title="BLAST 结果"
      extra={
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
      }
    >
      {/* ... */}
    </Card>
  );
};
```

### 3.3 后端实现 (Cookie Fallback)

```python
# routes/blast.py
from fastapi import Request, Cookie
from fastapi.responses import FileResponse

@router.get("/results/{task_id}")
async def get_blast_results(
    task_id: str,
    format: Literal["json", "xml", "text", "summary"] = "json",
    request: Request = None,
    token: Optional[str] = Cookie(None, alias="access_token"),
    current_user: User = Depends(get_current_user_optional),
):
    """
    返回 BLAST 结果，支持多种格式下载。
    认证方式优先级:
    1. Authorization Header (Bearer Token)
    2. Cookie: access_token
    """
    if current_user is None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            current_user = await verify_token(token)
        elif token:
            current_user = await verify_token(token)

    if current_user is None:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail=f"任务状态: {task.status}")

    result_path = task.result_path

    if format == "xml":
        return FileResponse(
            result_path,
            media_type="application/xml",
            filename=f"blast_{task_id}.xml"
        )
    elif format == "text":
        text_path = result_path.replace(".xml", ".txt")
        if not os.path.exists(text_path):
            convert_xml_to_text(result_path, text_path)
        return FileResponse(
            text_path,
            media_type="text/plain",
            filename=f"blast_{task_id}.txt"
        )
    elif format == "json":
        json_path = result_path.replace(".xml", ".json")
        if not os.path.exists(json_path):
            data = parse_blast_xml_to_dict(result_path)
            with open(json_path, "w") as f:
                json.dump(data, f)
        return FileResponse(
            json_path,
            media_type="application/json",
            filename=f"blast_{task_id}.json"
        )
    else:
        return {
            "task_id": task_id,
            "status": task.status,
            "hit_count": task.hit_count,
            "top_hit_identity": task.top_hit_identity,
            "top_hit_evalue": task.top_hit_evalue,
        }
```

---

## 四、问题 2 修复: 补充 Subject 详细信息

### 4.1 后端 XML 解析增强

```python
# utils/blast_xml_parser.py
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class BlastHsp:
    hsp_num: int
    bit_score: float
    evalue: float
    query_from: int
    query_to: int
    hit_from: int
    hit_to: int
    identity: int
    align_length: int
    mismatches: int
    gaps: int
    query_seq: str
    hit_seq: str
    midline: str

    @property
    def identity_percent(self) -> float:
        return (self.identity / self.align_length) * 100 if self.align_length > 0 else 0

@dataclass
class BlastHit:
    hit_num: int
    hit_id: str
    hit_def: str
    hit_accession: str
    hit_len: int
    hsps: List[BlastHsp]

    @property
    def best_hsp(self) -> Optional[BlastHsp]:
        return self.hsps[0] if self.hsps else None

    @property
    def subject_coverage(self) -> float:
        if self.best_hsp and self.hit_len > 0:
            return (self.best_hsp.align_length / self.hit_len) * 100
        return 0.0

    @property
    def total_score(self) -> float:
        return sum(hsp.bit_score for hsp in self.hsps)


def parse_blast_xml(xml_path: str) -> dict:
    """
    完整解析 BLAST XML (outfmt 5)，提取所有 Hit 元数据。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    query_len = int(root.findtext(".//BlastOutput_query-len", "0"))
    program = root.findtext(".//BlastOutput_program", "")
    db_name = root.findtext(".//BlastOutput_db", "")
    query_def = root.findtext(".//BlastOutput_query-def", "")

    hits = []
    for hit_elem in root.findall(".//Hit"):
        hit_num = int(hit_elem.findtext("Hit_num", "0"))
        hit_id = hit_elem.findtext("Hit_id", "")
        hit_def = hit_elem.findtext("Hit_def", "")
        hit_accession = hit_elem.findtext("Hit_accession", "")
        hit_len = int(hit_elem.findtext("Hit_len", "0"))

        hsps = []
        for hsp_elem in hit_elem.findall(".//Hsp"):
            hsps.append(BlastHsp(
                hsp_num=int(hsp_elem.findtext("Hsp_num", "0")),
                bit_score=float(hsp_elem.findtext("Hsp_bit-score", "0")),
                evalue=float(hsp_elem.findtext("Hsp_evalue", "0")),
                query_from=int(hsp_elem.findtext("Hsp_query-from", "0")),
                query_to=int(hsp_elem.findtext("Hsp_query-to", "0")),
                hit_from=int(hsp_elem.findtext("Hsp_hit-from", "0")),
                hit_to=int(hsp_elem.findtext("Hsp_hit-to", "0")),
                identity=int(hsp_elem.findtext("Hsp_identity", "0")),
                align_length=int(hsp_elem.findtext("Hsp_align-len", "0")),
                mismatches=int(hsp_elem.findtext("Hsp_mismatches", "0")),
                gaps=int(hsp_elem.findtext("Hsp_gaps", "0")),
                query_seq=hsp_elem.findtext("Hsp_qseq", ""),
                hit_seq=hsp_elem.findtext("Hsp_hseq", ""),
                midline=hsp_elem.findtext("Hsp_midline", ""),
            ))

        hits.append(BlastHit(
            hit_num=hit_num,
            hit_id=hit_id,
            hit_def=hit_def,
            hit_accession=hit_accession,
            hit_len=hit_len,
            hsps=hsps,
        ))

    return {
        "program": program,
        "db_name": db_name,
        "query_def": query_def,
        "query_len": query_len,
        "hit_count": len(hits),
        "hits": [
            {
                "hit_num": h.hit_num,
                "hit_id": h.hit_id,
                "hit_def": h.hit_def,
                "hit_accession": h.hit_accession,
                "hit_len": h.hit_len,
                "subject_coverage": round(h.subject_coverage, 2),
                "total_score": h.total_score,
                "best_hsp": {
                    "bit_score": h.best_hsp.bit_score,
                    "evalue": h.best_hsp.evalue,
                    "identity": h.best_hsp.identity,
                    "identity_percent": round(h.best_hsp.identity_percent, 2),
                    "align_length": h.best_hsp.align_length,
                    "query_from": h.best_hsp.query_from,
                    "query_to": h.best_hsp.query_to,
                    "hit_from": h.best_hsp.hit_from,
                    "hit_to": h.best_hsp.hit_to,
                    "mismatches": h.best_hsp.mismatches,
                    "gaps": h.best_hsp.gaps,
                    "query_seq": h.best_hsp.query_seq,
                    "hit_seq": h.best_hsp.hit_seq,
                    "midline": h.best_hsp.midline,
                } if h.best_hsp else None,
                "hsps": [
                    {
                        "query_from": hh.query_from,
                        "query_to": hh.query_to,
                        "hit_from": hh.hit_from,
                        "hit_to": hh.hit_to,
                        "identity_percent": round(hh.identity_percent, 2),
                        "evalue": hh.evalue,
                        "bit_score": hh.bit_score,
                    }
                    for hh in h.hsps
                ],
            }
            for h in hits
        ],
    }
```

### 4.2 前端结果表格增强

```tsx
// src/pages/Blast/BlastResultPage.tsx
const columns = [
  {
    title: "#",
    dataIndex: "hit_num",
    width: 50,
    render: (v: number) => <strong>{v}</strong>,
  },
  {
    title: "Subject ID",
    dataIndex: "hit_accession",
    width: 120,
    render: (v: string, record: any) => (
      <Tooltip content={record.hit_id}>
        <span style={{ fontFamily: "monospace", fontSize: 12 }}>{v}</span>
      </Tooltip>
    ),
  },
  {
    title: "Subject Description",
    dataIndex: "hit_def",
    width: 280,
    ellipsis: true,
    render: (v: string) => <span style={{ fontSize: 13 }}>{v}</span>,
  },
  {
    title: "Subject Length",
    dataIndex: "hit_len",
    width: 100,
    render: (v: number) => `${v.toLocaleString()} bp`,
  },
  {
    title: "Identity %",
    dataIndex: ["best_hsp", "identity_percent"],
    width: 90,
    sorter: (a: any, b: any) => a.best_hsp.identity_percent - b.best_hsp.identity_percent,
    render: (v: number) => {
      let color = "red";
      if (v >= 90) color = "green";
      else if (v >= 70) color = "blue";
      else if (v >= 40) color = "orange";
      return <Tag color={color}>{v.toFixed(1)}%</Tag>;
    },
  },
  {
    title: "E-value",
    dataIndex: ["best_hsp", "evalue"],
    width: 110,
    sorter: (a: any, b: any) => a.best_hsp.evalue - b.best_hsp.evalue,
    render: (v: number) => {
      if (v < 1e-100) return <Tag color="red" size="small">{v.toExponential(1)}</Tag>;
      if (v < 1e-10) return <Tag color="orange" size="small">{v.toExponential(1)}</Tag>;
      return <span>{v.toExponential(2)}</span>;
    },
  },
  {
    title: "Bit Score",
    dataIndex: ["best_hsp", "bit_score"],
    width: 90,
    sorter: (a: any, b: any) => a.best_hsp.bit_score - b.best_hsp.bit_score,
  },
  {
    title: "Align Length",
    dataIndex: ["best_hsp", "align_length"],
    width: 90,
    render: (v: number) => `${v} bp`,
  },
  {
    title: "Query Range",
    dataIndex: "best_hsp",
    width: 110,
    render: (hsp: any) => `${hsp.query_from}-${hsp.query_to}`,
  },
  {
    title: "Subject Range",
    dataIndex: "best_hsp",
    width: 110,
    render: (hsp: any) => `${hsp.hit_from}-${hsp.hit_to}`,
  },
  {
    title: "Subject Coverage",
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

## 五、问题 3 修复: 比对可视化

### 5.1 比对条可视化组件 (SVG)

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
}

const BlastAlignmentBar: React.FC<BlastAlignmentBarProps> = ({
  hitLen,
  hsps,
  barHeight = 24,
}) => {
  const svgWidth = 600;
  const padding = { left: 60, right: 60 };
  const scale = (pos: number) =>
    padding.left + (pos / hitLen) * (svgWidth - padding.left - padding.right);

  const getColor = (identity: number) => {
    if (identity >= 90) return "#10b981";
    if (identity >= 70) return "#3b82f6";
    if (identity >= 40) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <svg width="100%" viewBox={`0 0 ${svgWidth} ${barHeight + 20}`} style={{ fontFamily: "monospace", fontSize: 10 }}>
      <line
        x1={padding.left}
        y1={barHeight / 2 + 10}
        x2={svgWidth - padding.right}
        y2={barHeight / 2 + 10}
        stroke="#e5e7eb"
        strokeWidth={2}
      />
      <text x={padding.left - 5} y={barHeight / 2 + 14} textAnchor="end" fill="#6b7280">1</text>
      <text x={svgWidth - padding.right + 5} y={barHeight / 2 + 14} textAnchor="start" fill="#6b7280">
        {hitLen.toLocaleString()}
      </text>
      {hsps.map((hsp, idx) => {
        const x = scale(hsp.hit_from);
        const width = scale(hsp.hit_to) - x;
        const color = getColor(hsp.identity_percent);
        return (
          <Tooltip
            key={idx}
            content={
              <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                <div><strong>Subject Range:</strong> {hsp.hit_from}-{hsp.hit_to}</div>
                <div><strong>Query Range:</strong> {hsp.query_from}-{hsp.query_to}</div>
                <div><strong>Identity:</strong> {hsp.identity_percent.toFixed(1)}%</div>
                <div><strong>E-value:</strong> {hsp.evalue.toExponential(2)}</div>
                <div><strong>Bit Score:</strong> {hsp.bit_score}</div>
              </div>
            }
          >
            <rect
              x={x}
              y={10}
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

### 5.2 序列对齐彩色视图

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
  const lines: { q: string; m: string; s: string; qStart: number; sStart: number }[] = [];

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

  const getBaseColor = (qBase: string, mChar: string) => {
    if (mChar === "|") return "#10b981";
    if (mChar === "+") return "#f59e0b";
    if (qBase === "-") return "#9ca3af";
    return "#ef4444";
  };

  return (
    <Card size="small" title="序列比对详情" style={{ marginTop: 16, fontFamily: "monospace" }}>
      <div style={{ overflowX: "auto", whiteSpace: "nowrap" }}>
        {lines.map((line, idx) => (
          <div key={idx} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 80, textAlign: "right", color: "#6b7280", fontSize: 12 }}>
                Query {line.qStart}
              </span>
              <span>
                {line.q.split("").map((base, i) => (
                  <span
                    key={i}
                    style={{
                      color: getBaseColor(base, line.m[i]),
                      fontWeight: line.m[i] === "|" ? 600 : 400,
                      backgroundColor: line.m[i] === "|" ? "#ecfdf5" : "transparent",
                      padding: "0 1px",
                    }}
                  >
                    {base}
                  </span>
                ))}
              </span>
              <span style={{ color: "#6b7280", fontSize: 12 }}>
                {line.qStart + line.q.replace(/-/g, "").length - 1}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 88 }}>
              <span style={{ color: "#9ca3af", letterSpacing: "1px" }}>{line.m}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 80, textAlign: "right", color: "#6b7280", fontSize: 12 }}>
                Sbjct {line.sStart}
              </span>
              <span>
                {line.s.split("").map((base, i) => (
                  <span
                    key={i}
                    style={{
                      color: getBaseColor(base, line.m[i]),
                      fontWeight: line.m[i] === "|" ? 600 : 400,
                      backgroundColor: line.m[i] === "|" ? "#ecfdf5" : "transparent",
                      padding: "0 1px",
                    }}
                  >
                    {base}
                  </span>
                ))}
              </span>
              <span style={{ color: "#6b7280", fontSize: 12 }}>
                {line.sStart + line.s.replace(/-/g, "").length - 1}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #e5e7eb", fontSize: 12 }}>
        <span style={{ marginRight: 16 }}><span style={{ color: "#10b981" }}>■</span> 完全匹配 (|)</span>
        <span style={{ marginRight: 16 }}><span style={{ color: "#f59e0b" }}>■</span> 相似匹配 (+)</span>
        <span style={{ marginRight: 16 }}><span style={{ color: "#ef4444" }}>■</span> 错配</span>
        <span><span style={{ color: "#9ca3af" }}>■</span> Gap (-)</span>
      </div>
    </Card>
  );
};

export default BlastSequenceAlignment;
```

### 5.3 结果页整合

```tsx
// BlastResultPage.tsx 整合
import BlastAlignmentBar from "@/components/Blast/BlastAlignmentBar";
import BlastSequenceAlignment from "@/components/Blast/BlastSequenceAlignment";

// 在表格上方添加 Hit 分布图
<Card size="small" title="比对结果分布" style={{ marginBottom: 16 }}>
  {resultData?.hits?.map((hit: any) => (
    <div key={hit.hit_num} style={{ marginBottom: 8, display: "flex", alignItems: "center" }}>
      <span style={{ width: 40, fontSize: 12, color: "#6b7280" }}>#{hit.hit_num}</span>
      <span style={{ width: 120, fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {hit.hit_accession}
      </span>
      <div style={{ flex: 1 }}>
        <BlastAlignmentBar
          hitLen={hit.hit_len}
          hsps={hit.hsps || [hit.best_hsp]}
          queryLen={resultData.query_len}
        />
      </div>
    </div>
  ))}
</Card>

// 表格展开行显示序列对齐
<Table
  columns={columns}
  data={resultData?.hits || []}
  rowKey="hit_num"
  expandedRowRender={(record: any) => (
    <BlastSequenceAlignment
      querySeq={record.best_hsp.query_seq}
      hitSeq={record.best_hsp.hit_seq}
      midline={record.best_hsp.midline}
      queryFrom={record.best_hsp.query_from}
      hitFrom={record.best_hsp.hit_from}
    />
  )}
  expandProps={{
    icon: ({ expanded }: { expanded: boolean }) => (
      <Button type="text" size="mini">{expanded ? "收起" : "展开对齐"}</Button>
    ),
  }}
/>
```

---

## 六、后端 Celery 任务修改

```python
# tasks/blast_search.py

def parse_blast_xml(xml_path: str) -> dict:
    """增强版 XML 解析，提取完整的 Hit 元数据。"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    query_len = int(root.findtext(".//BlastOutput_query-len", "0"))
    program = root.findtext(".//BlastOutput_program", "")
    db_name = root.findtext(".//BlastOutput_db", "")
    query_def = root.findtext(".//BlastOutput_query-def", "")

    hits = []
    for hit_elem in root.findall(".//Hit"):
        hit_num = int(hit_elem.findtext("Hit_num", "0"))
        hit_id = hit_elem.findtext("Hit_id", "")
        hit_def = hit_elem.findtext("Hit_def", "")
        hit_accession = hit_elem.findtext("Hit_accession", "")
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
        hits.append({
            "hit_num": hit_num,
            "hit_id": hit_id,
            "hit_def": hit_def,
            "hit_accession": hit_accession,
            "hit_len": hit_len,
            "subject_coverage": round((best_hsp["align_length"] / hit_len) * 100, 2) if best_hsp else 0,
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

## 七、验收标准

### 7.1 下载功能
- [ ] 点击 XML/JSON/Text 下载按钮，浏览器正常下载文件，不再提示 401
- [ ] 下载的文件内容完整，与服务器存储一致
- [ ] 未登录状态下访问下载链接，正确返回 401 或跳转登录页

### 7.2 Subject 信息
- [ ] 结果表格显示 Subject ID (Accession) 列
- [ ] 结果表格显示 Subject Description 列，过长时 ellipsis 显示
- [ ] 结果表格显示 Subject Length 列，格式为 "553 bp"
- [ ] 结果表格显示 Subject Coverage 列，带 Progress 进度条
- [ ] 结果表格支持按 Identity、E-value、Bit Score、Subject Coverage 排序

### 7.3 可视化
- [ ] 表格上方显示比对分布条，每个 Hit 一条横向 bar
- [ ] Bar 颜色根据 Identity 编码：绿(>=90%) / 蓝(>=70%) / 橙(>=40%) / 红(<40%)
- [ ] Hover bar 显示详细统计（Range、Identity、E-value、Bit Score）
- [ ] 点击表格行展开序列对齐详情，完全匹配显示绿色，错配显示红色，Gap 显示灰色
- [ ] 序列对齐显示 Query/Sbjct 位置标尺
- [ ] 页面在 1000 hits 下加载时间 < 3s

---

## 八、修改文件清单

| 文件路径 | 修改类型 | 说明 |
|----------|----------|------|
| `src/utils/downloadFile.ts` | 新增 | 带认证的通用下载工具 |
| `src/pages/Blast/BlastResultPage.tsx` | 修改 | 替换下载逻辑，增强表格列，整合可视化组件 |
| `src/components/Blast/BlastAlignmentBar.tsx` | 新增 | SVG 比对条可视化 |
| `src/components/Blast/BlastSequenceAlignment.tsx` | 新增 | 彩色序列对齐视图 |
| `backend/utils/blast_xml_parser.py` | 修改 | 增强解析，提取 Hit 元数据 |
| `backend/tasks/blast_search.py` | 修改 | 更新 parse_blast_xml，生成完整 JSON 缓存 |
| `backend/routes/blast.py` | 修改 | 下载 API 支持 Cookie fallback |

---

## 九、附录: 颜色编码规范

| Identity 范围 | 颜色 | Hex | 含义 |
|---------------|------|-----|------|
| >= 90% | 绿色 | #10b981 | 高度相似 |
| >= 70% | 蓝色 | #3b82f6 | 较相似 |
| >= 40% | 橙色 | #f59e0b | 中等相似 |
| < 40% | 红色 | #ef4444 | 低相似 |

---

## 十、版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|----------|------|
| v1.1 | 2026-07-15 | 问题诊断 + 优化方案 | Kimi |
