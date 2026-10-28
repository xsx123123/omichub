# OmicHub BLAST 结果页面优化方案 v1.4

> 日期: 2026-07-15  
> 问题: 1) 数据库显示路径而非名称; 2) 参数说明位置不对; 3) Subject ID 仍显示错误  
> 目标: 精准修复，最小改动

---

## 一、问题精准诊断

### 问题 1: 数据库显示为文件路径 `/data/omichub/blast/db/111/111`

**截图证据:** 顶部统计摘要显示 "数据库: /data/omichub/blast/db/111/111"

**根因:**
后端从 BLAST XML 中取的 `db_name` 是 `makeblastdb` 时传入的 `-db` 路径，即文件路径。而用户期望看到的是数据库的**显示名称**（如 "TRA10"）。

**修复:** 后端查询任务时，通过 `db_id` 关联 `blast_databases` 表，取 `name` 字段返回。

---

### 问题 2: 参数说明在右侧信息面板，应该放在结果区域

**截图证据:** 右侧信息面板有 "参数说明" 卡片，但结果区域（表格上方）没有。

**用户期望:** 参数说明应该放在比对结果表格上方，作为结果的一部分，方便用户查看结果时对照参数含义。

**修复:** 前端把 "参数说明" 从 `BlastRightPanel` 移到 `BlastResultPage` 的结果区域，放在表格上方。

---

### 问题 3: Subject ID 仍显示 "CHROMOSOME"

**截图证据:** 表格 Subject ID 列: `CHROMOSOME`

**根因分析:**
之前的修复方案假设 `Hit_accession` = `Chr1`，但实际可能：
1. Celery 任务生成的旧 JSON 缓存没有被重新生成（XML 解析改了但 JSON 文件还是旧的）
2. 或者 `Hit_accession` 确实是数字，而 `Chr1` 在 `Hit_id` 字段里（如 `lcl|Chr1`）

**快速验证:** 你需要在服务器上查看原始 XML 的 Hit 节点：

```bash
# 找到结果 XML 文件
ls /data/omichub/blast_results/{user_id}/{task_id}.xml

# 查看 Hit 节点
grep -A 5 "<Hit>" /data/omichub/blast_results/{user_id}/{task_id}.xml | head -20
```

**修复策略:** 后端解析时增加多层 fallback，确保能提取到 `Chr1`：
1. 优先 `Hit_accession`（如果非数字）
2. 其次解析 `Hit_id`（处理 `lcl|Chr1` 格式）
3. 最后回退 `Hit_def` 切分

同时，**删除旧 JSON 缓存**，让 Celery 重新生成。

---

## 二、后端修复

### 2.1 修改结果查询 API，返回数据库名称

```python
# backend/routes/blast.py

@router.get("/results/{task_id}")
async def get_blast_results(
    task_id: str,
    format: Literal["json", "xml", "text", "summary"] = "json",
    current_user: User = Depends(get_current_user),
):
    task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail=f"任务状态: {task.status}")

    # ===== 修复 1: 关联数据库表获取显示名称 =====
    blast_db = db.query(BlastDatabase).filter(BlastDatabase.id == task.db_id).first()
    db_display_name = blast_db.name if blast_db else "Unknown"
    db_key = blast_db.db_key if blast_db else ""

    if format == "json":
        json_path = task.result_path.replace(".xml", ".json")

        # 如果 JSON 不存在或需要刷新，重新解析
        if not os.path.exists(json_path):
            data = parse_blast_xml_to_dict(task.result_path)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        else:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        # 注入数据库显示名称和查询参数
        data["db_display_name"] = db_display_name
        data["db_key"] = db_key
        data["query_params"] = {
            "evalue": task.evalue,
            "max_target_seqs": task.max_target_seqs,
            "word_size": task.word_size,
            "gapopen": task.gapopen,
            "gapextend": task.gapextend,
            "program": task.program,
        }

        return data

    # ... XML 和 Text 返回逻辑不变
```

### 2.2 修复 XML 解析，确保提取 Chr1

```python
# backend/utils/blast_xml_parser.py

def extract_hit_id(hit_elem) -> tuple[str, str]:
    """
    从 Hit 节点提取序列 ID 和描述。
    返回: (hit_id, hit_desc)
    """
    hit_def = hit_elem.findtext("Hit_def", "")
    hit_accession = hit_elem.findtext("Hit_accession", "")
    hit_id_raw = hit_elem.findtext("Hit_id", "")

    hit_id = ""
    hit_desc = ""

    # 策略 1: Hit_accession 非数字且非空
    if hit_accession and not hit_accession.isdigit():
        hit_id = hit_accession.strip()
        hit_desc = hit_def.strip()
        return hit_id, hit_desc

    # 策略 2: 解析 Hit_id (如 lcl|Chr1, gnl|BL_ORD_ID|0)
    if hit_id_raw and "|" in hit_id_raw:
        parts = hit_id_raw.split("|")
        # lcl|Chr1 -> Chr1; gnl|BL_ORD_ID|0 -> 0 (数字，跳过)
        if len(parts) >= 2:
            candidate = parts[-1].strip()
            if candidate and not candidate.isdigit():
                hit_id = candidate
                hit_desc = hit_def.strip()
                return hit_id, hit_desc

    # 策略 3: 从 Hit_def 按空格切分
    if hit_def:
        parts = hit_def.split(" ", 1)
        hit_id = parts[0].strip()
        hit_desc = parts[1].strip() if len(parts) > 1 else ""

    return hit_id, hit_desc


def parse_blast_xml_to_dict(xml_path: str) -> dict:
    """解析 BLAST XML 为前端友好的 JSON。"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    query_len = int(root.findtext(".//BlastOutput_query-len", "0"))
    program = root.findtext(".//BlastOutput_program", "")
    db_name = root.findtext(".//BlastOutput_db", "")  # 这是文件路径
    query_def = root.findtext(".//BlastOutput_query-def", "")

    hits = []
    for hit_elem in root.findall(".//Hit"):
        hit_id, hit_desc = extract_hit_id(hit_elem)
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
            "hit_id": hit_id,                    # 应该是 Chr1
            "hit_def": hit_desc,                # 描述
            "hit_accession": hit_elem.findtext("Hit_accession", ""),
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
        "db_name": db_name,  # 保留原始路径，前端可用 db_display_name
        "query_def": query_def,
        "query_len": query_len,
        "hit_count": len(hits),
        "hits": hits,
    }
```

### 2.3 清除旧缓存

```bash
# 在服务器上执行，删除旧的 JSON 缓存，让下次请求时重新生成
find /data/omichub/blast_results/ -name "*.json" -delete

# 或者只删除特定任务的
rm /data/omichub/blast_results/{user_id}/{task_id}.json
```

---

## 三、前端修复

### 3.1 从右侧面板移除参数说明

```tsx
// src/pages/Blast/BlastRightPanel.tsx
// 删除 ParameterHelpCard 相关代码，或标记为已移除

// 删除以下整个 renderHelpCard 函数和调用
// const renderHelpCard = () => (
//   <Card size="small" title="参数说明" style={{ marginBottom: 16 }}>
//     ...
//   </Card>
// );

// 在 return 中删除 {renderHelpCard()}
```

### 3.2 在结果页添加参数说明（表格上方）

```tsx
// src/pages/Blast/BlastResultPage.tsx
import React from "react";
import { Card, Table, Tag, Space, Descriptions } from "@arco-design/web-react";

// 参数说明组件
const BlastParamsInfo: React.FC<{ params: any }> = ({ params }) => {
  if (!params) return null;

  const items = [
    { label: "E-value", value: params.evalue, desc: "随机出现同等匹配的期望次数，越小越严格。" },
    { label: "最大匹配数", value: params.max_target_seqs, desc: "限制返回的目标序列数量，避免结果过大。" },
    { label: "Word Size", value: params.word_size || "默认", desc: "初始种子长度；越小越敏感，但计算更慢。" },
    { label: "Gap Open/Extend", value: params.gapopen ? `${params.gapopen}/${params.gapextend}` : "默认", desc: "控制插入缺失的开启和延伸罚分。" },
  ];

  return (
    <Card size="small" title="查询参数" style={{ marginBottom: 12 }} bodyStyle={{ padding: "8px 12px" }}>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {items.map((item) => (
          <Tooltip key={item.label} content={item.desc}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
              <span style={{ color: "#6b7280" }}>{item.label}:</span>
              <Tag size="small" style={{ fontSize: 12 }}>{item.value}</Tag>
            </div>
          </Tooltip>
        ))}
      </div>
    </Card>
  );
};

// 在 BlastResultPage 的 return 中，放在 Graphic Summary 和表格之间
const BlastResultPage: React.FC = () => {
  // ... loading 和 data 获取逻辑

  const { hit_count, query_len, hits, db_display_name, program, query_params } = resultData || {};

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      {/* 统计摘要 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space size="large">
          <Statistic title="数据库" value={db_display_name || "-"} />  {/* 修复 1: 显示名称 */}
          <Statistic title="算法" value={program?.toUpperCase()} />
          <Statistic title="Query 长度" value={`${query_len} bp`} />
          <Statistic title="命中数" value={hit_count} />
        </Space>

        <Divider style={{ margin: "12px 0" }} />

        <Space>
          <Button size="small" onClick={() => handleDownload("xml")}>XML</Button>
          <Button size="small" onClick={() => handleDownload("json")}>JSON</Button>
          <Button size="small" onClick={() => handleDownload("text")}>Text</Button>
        </Space>
      </Card>

      {/* Graphic Summary */}
      {hit_count > 0 && <BlastGraphicSummary queryLen={query_len} hits={hits} />}

      {/* 修复 2: 参数说明移到结果区域 */}
      {query_params && <BlastParamsInfo params={query_params} />}

      {/* 比对结果表格 */}
      <Card size="small" title="比对结果" style={{ marginBottom: 16 }}>
        <Table columns={columns} data={hits || []} rowKey="hit_num" pagination={{ pageSize: 20 }} />
      </Card>

      {/* Hit 详情卡片 */}
      {/* ... */}
    </div>
  );
};
```

### 3.3 右侧信息面板精简

```tsx
// src/pages/Blast/BlastRightPanel.tsx
// 移除参数说明后，右侧只保留序列分析和最近任务

const BlastRightPanel: React.FC<BlastRightPanelProps> = ({
  sequenceStats,
  recentTasks,
  loadingTasks,
}) => {
  return (
    <div style={{ paddingLeft: 24 }}>
      {renderSequenceCard()}
      {renderHistoryCard()}
      {/* 参数说明已移除 */}
    </div>
  );
};
```

---

## 四、验证步骤

### 步骤 1: 确认 XML 中的 Hit 结构

```bash
# 在服务器上查看你的结果 XML
cat /data/omichub/blast_results/{user_id}/{task_id}.xml | grep -A 8 "<Hit>" | head -20
```

期望看到：
```xml
<Hit>
  <Hit_num>1</Hit_num>
  <Hit_id>lcl|Chr1</Hit_id>          <!-- 或 gnl|BL_ORD_ID|0 -->
  <Hit_def>CHROMOSOME dumped...</Hit_def>
  <Hit_accession>Chr1</Hit_accession>  <!-- 或 0 -->
  <Hit_len>30427671</Hit_len>
```

把输出贴给我，我确认 `Chr1` 到底在哪个字段。

### 步骤 2: 清除 JSON 缓存并重新请求

```bash
# 删除旧缓存
rm /data/omichub/blast_results/{user_id}/{task_id}.json

# 然后在前端刷新页面，后端会重新解析 XML 生成 JSON
```

### 步骤 3: 检查返回的 JSON

浏览器 DevTools → Network → 找到 `/api/blast/results/{task_id}?format=json` → Preview

确认：
- `db_display_name` = "TRA10"（或你的数据库名称）
- `hits[0].hit_id` = "Chr1"
- `query_params` 包含 evalue、max_target_seqs 等

---

## 五、修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/routes/blast.py` | 关联 `blast_databases` 表获取 `name`，注入 `db_display_name` 和 `query_params` |
| `backend/utils/blast_xml_parser.py` | `extract_hit_id()` 多层 fallback，确保提取 `Chr1` |
| `src/pages/Blast/BlastResultPage.tsx` | 顶部显示 `db_display_name`；新增 `BlastParamsInfo` 组件；参数说明移到结果区域 |
| `src/pages/Blast/BlastRightPanel.tsx` | 移除参数说明卡片 |

---

## 六、如果 Subject ID 还是不对

如果按上述修复后，Subject ID 仍然显示 "CHROMOSOME"，请执行以下命令并把输出贴给我：

```bash
# 1. 查看 XML 中的 Hit 节点
cat /data/omichub/blast_results/{user_id}/{task_id}.xml | python3 -c "
import sys, xml.etree.ElementTree as ET
tree = ET.parse(sys.stdin)
for hit in tree.findall('.//Hit'):
    print('Hit_num:', hit.findtext('Hit_num'))
    print('Hit_id:', hit.findtext('Hit_id'))
    print('Hit_accession:', hit.findtext('Hit_accession'))
    print('Hit_def:', hit.findtext('Hit_def')[:80])
    print('---')
"

# 2. 查看数据库中的 db_key 和 name
# 在 PostgreSQL 中执行
SELECT id, name, db_key, file_path FROM blast_databases WHERE name = 'TRA10';
```
