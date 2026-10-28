# AI 助手 & AI 工作台通用任务能力排查报告

## 概述

本文档排查了 OmicHub 平台 AI 助手和 AI 工作台对以下通用任务的处理能力：
1. **XLSX 文件处理**（Excel 表格读取、分析、导出）
2. **PDF 文献阅读**（上传 PDF、提取文本、内容理解）
3. **文献汇总**（检索文献、整理摘要、生成综述）

---

## 一、XLSX 文件处理能力

### 1.1 能力状态：✅ 已支持

### 1.2 环境依赖

| 组件 | 版本 | 位置 |
|------|------|------|
| `openpyxl` | 3.1.5 | `deploy/studio/base.Dockerfile` |
| `pandas` | 2.2.3 | `deploy/studio/base.Dockerfile` |
| `openpyxl` | 3.1 | `deploy/sandbox/Dockerfile` |
| `pandas` | 2.2.2 | `deploy/sandbox/Dockerfile` |

### 1.3 使用方式

#### AI 工作台（Studio）
- 用户上传 XLSX 文件到工作区
- 通过 `datahub_import` 工具引入到沙盒 `/workspace/input/`
- 在沙盒中用 `pandas.read_excel()` 直接读取
- 提示词明确说明："引入后即可用 pandas 等直接读取"

#### 普通聊天
- 通过 `chat_sandbox_execute` 工具执行 Python 代码
- 需要交付的文件写入 `/tmp/chat_output/`
- 平台自动收集产物并提供下载

### 1.4 提示词约束（`data/ai/prompts/general.md`）

```markdown
### 数值计算与表格处理（强制沙盒执行）

- 对 `xlsx` / `xls` / `csv` / `tsv`，先实际读取并报告工作簿 sheet、列名、行数、
  数据类型和缺失值；公式、分组、去重、异常值或汇总口径不明确时必须调用 `ask_user` 澄清。
- 原始输入文件保持只读，不得覆盖。脚本写入 `scripts/`，结果写入 `output/results/`；
  交付时报告输入文件、使用的 sheet、计算公式、关键数值、实际 Python 输出和结果文件路径。
- 宏文件、加密文件、外部链接公式或超大工作簿必须说明限制并给出安全降级方案。
```

### 1.5 限制

| 限制项 | 说明 |
|--------|------|
| 宏文件 | 需说明限制，给出安全降级方案 |
| 加密文件 | 需说明限制，给出安全降级方案 |
| 外部链接公式 | 需说明限制，给出安全降级方案 |
| 超大工作簿 | 需说明限制，给出安全降级方案 |
| 文件只读 | 原始输入文件不得覆盖 |

---

## 二、PDF 文献阅读能力

### 2.1 能力状态：⚠️ 部分支持

### 2.2 环境依赖

| 组件 | 用途 | 位置 |
|------|------|------|
| `pypdf` | PDF 文本提取 | Python 依赖（通过 `pyproject.toml`） |

### 2.3 使用方式

#### 聊天附件上传
- 用户上传 PDF 作为聊天附件
- 系统通过 `_read_attachment_text()` 读取
- 调用 `_extract_pdf_text()` 提取分页文本
- 文本限制：最多 24,000 字符（约 10-15 页）

#### 代码实现
```python
# chat_service.py
@staticmethod
def _extract_pdf_text(source: str | bytes) -> str:
    """提取聊天 PDF 的分页文本，避免把二进制内容按 UTF-8 注入模型。"""
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(source) if isinstance(source, bytes) else source)
    pages: list[str] = []
    total_chars = 0
    max_chars = 24_000
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        pages.append(f"[第 {page_number} 页]\n{text[:remaining]}")
        total_chars += len(text)
    return "\n\n".join(pages)
```

### 2.4 限制

| 限制项 | 说明 |
|--------|------|
| 文本长度 | 最多 24,000 字符（约 10-15 页） |
| 扫描件 PDF | 无法提取文本（需要 OCR） |
| 工作区文件 | PDF 被列为二进制文件，`workspace_read_file` 不直接读取内容 |
| 沙盒环境 | 沙盒镜像未预装 `pypdf`，需现场安装 |

### 2.5 工作区文件处理

```python
# presets.py - _BINARY_ONLY_SUFFIXES
_BINARY_ONLY_SUFFIXES = frozenset({
    ".bam", ".cram", ".bai", ".crai", ".fastq", ".fq", ".fastq.gz", ".fq.gz",
    ".h5ad", ".h5", ".rds", ".rdata", ".loom", ".bw", ".bigwig", ".2bit",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tiff",
    ".pdf", ".db", ".sqlite",  # ← PDF 在此列表中
})
```

**影响**：通过 `workspace_read_file` 读取工作区 PDF 时，只返回元数据，不返回内容。

---

## 三、文献汇总能力

### 3.1 能力状态：✅ 已支持

### 3.2 文献检索工具

#### Europe PMC 检索
```yaml
# data/ai/tools/research.yaml
id: research
description: 联网证据检索配合 KEGG 富集分析。
platform_tools:
  - europe_pmc_search
builtin_tools:
  - omichub_run_kegg_enrichment
```

#### 工具功能
- 检索 Europe PMC 权威生物医学论文
- 按用户问题对标题与摘要进行语义/词项混合重排
- 返回题名、摘要、作者、期刊、年份、PMID/PMCID/DOI
- 开放获取状态和可追溯链接
- 只读且不下载全文

#### 代码实现
```python
# biomedical_literature_service.py
class BiomedicalLiteratureService:
    ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    
    async def search(
        self,
        query: str,
        max_results: int = 8,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
        open_access_only: bool = False,
    ) -> list[dict[str, Any]]:
        # 返回结构化文献数据
```

### 3.3 文献汇总流程

1. **检索阶段**
   - 调用 `europe_pmc_search` 检索相关文献
   - 支持年份范围、开放获取过滤
   - 返回最相关的 5-8 篇

2. **阅读阶段**
   - 通过附件上传 PDF（受 24,000 字符限制）
   - 或基于摘要进行理解

3. **汇总阶段**
   - AI 模型基于检索结果和上传文献生成汇总
   - 可调用 `parallel_subagents` 并行处理多个子任务

### 3.4 限制

| 限制项 | 说明 |
|--------|------|
| 全文获取 | 只检索摘要，不下载全文 |
| PDF 阅读 | 受 24,000 字符限制，长文献无法完整阅读 |
| 文献来源 | 仅支持 Europe PMC，不支持 PubMed 直接检索 |
| 非生物医学 | 非生物医学领域文献检索能力有限 |

---

## 四、综合任务场景分析

### 4.1 场景：处理 XLSX 并生成报告

**流程**：
1. 用户上传 XLSX 文件
2. 通过 `datahub_import` 引入沙盒
3. 在沙盒中用 pandas 读取分析
4. 生成结果写入 `/tmp/chat_output/`
5. 平台自动提供下载

**能力**：✅ 完全支持

### 4.2 场景：阅读 PDF 文献并汇总

**流程**：
1. 用户上传 PDF 作为附件
2. 系统提取文本（最多 24,000 字符）
3. AI 理解内容并生成摘要

**能力**：️ 部分支持（受文本长度限制）

### 4.3 场景：检索文献并生成综述

**流程**：
1. 调用 `europe_pmc_search` 检索相关文献
2. 基于摘要理解文献内容
3. 生成文献综述

**能力**：✅ 支持（基于摘要）

### 4.4 场景：完整工作流（XLSX + PDF + 文献汇总）

**流程**：
1. 上传 XLSX 数据文件 → 沙盒分析
2. 上传 PDF 文献 → 文本提取（受限制）
3. 检索 Europe PMC → 获取相关文献摘要
4. 综合生成报告

**能力**：⚠️ 部分支持（PDF 阅读是瓶颈）

---

## 五、优化建议

### 5.1 PDF 阅读能力增强

| 优化项 | 建议 |
|--------|------|
| 文本长度限制 | 从 24,000 字符提升到 50,000+ 字符 |
| 工作区 PDF 读取 | 允许 `workspace_read_file` 读取 PDF 文本内容 |
| 沙盒 PDF 库 | 在沙盒镜像中预装 `pypdf` 或 `PyMuPDF` |
| OCR 支持 | 考虑添加扫描件 PDF 的 OCR 能力 |

### 5.2 文献检索增强

| 优化项 | 建议 |
|--------|------|
| 多源检索 | 添加 PubMed、arXiv 等检索源 |
| 全文获取 | 支持开放获取文献的全文下载 |
| 文献管理 | 添加文献收藏、笔记功能 |

### 5.3 XLSX 处理增强

| 优化项 | 建议 |
|--------|------|
| 大文件支持 | 优化超大 Excel 文件的处理策略 |
| 模板支持 | 提供常用分析模板 |
| 可视化 | 增强 Excel 数据的可视化能力 |

---

## 六、总结

| 任务类型 | 能力状态 | 主要限制 |
|----------|----------|----------|
| XLSX 处理 | ✅ 完全支持 | 宏/加密/超大文件需降级处理 |
| PDF 阅读 | ️ 部分支持 | 24,000 字符限制，工作区文件不直接读取 |
| 文献检索 | ✅ 完全支持 | 仅 Europe PMC，只返回摘要 |
| 文献汇总 | ✅ 支持 | 依赖摘要，全文阅读受限 |

**核心瓶颈**：PDF 文献的完整阅读能力是当前最大的限制因素。建议优先解决：
1. 提升 PDF 文本提取长度限制
2. 允许工作区 PDF 文件的文本读取
3. 在沙盒环境中预装 PDF 处理库
