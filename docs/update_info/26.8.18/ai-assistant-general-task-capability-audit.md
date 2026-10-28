# AI Assistant & AI Workbench General Task Capability Audit Report

## Overview

This document audits OmicHub platform's AI Assistant and AI Workbench capabilities for the following general tasks:
1. **XLSX File Processing** (Excel reading, analysis, export)
2. **PDF Literature Reading** (upload PDF, extract text, content understanding)
3. **Literature Summarization** (search literature, organize abstracts, generate reviews)

---

## 1. XLSX File Processing Capability

### 1.1 Status: ✅ Fully Supported

### 1.2 Environment Dependencies

| Component | Version | Location |
|-----------|---------|----------|
| `openpyxl` | 3.1.5 | `deploy/studio/base.Dockerfile` |
| `pandas` | 2.2.3 | `deploy/studio/base.Dockerfile` |
| `openpyxl` | 3.1 | `deploy/sandbox/Dockerfile` |
| `pandas` | 2.2.2 | `deploy/sandbox/Dockerfile` |

### 1.3 Usage Methods

#### AI Workbench (Studio)
- User uploads XLSX file to workspace
- Import to sandbox `/workspace/input/` via `datahub_import` tool
- Read directly with `pandas.read_excel()` in sandbox
- Prompt explicitly states: "引入后即可用 pandas 等直接读取" (ready to read with pandas after import)

#### Regular Chat
- Execute Python code via `chat_sandbox_execute` tool
- Files for delivery written to `/tmp/chat_output/`
- Platform automatically collects artifacts and provides download

### 1.4 Prompt Constraints (`data/ai/prompts/general.md`)

```markdown
### Numerical Computation & Table Processing (Mandatory Sandbox Execution)

- For `xlsx` / `xls` / `csv` / `tsv`, first actually read and report workbook sheets, 
  column names, row counts, data types and missing values; when formulas, grouping, 
  deduplication, outliers or aggregation criteria are unclear, must call `ask_user` for clarification.
- Original input files remain read-only, must not be overwritten. Scripts go to `scripts/`, 
  results to `output/results/`; delivery reports input file, used sheet, calculation formulas, 
  key values, actual Python output and result file path.
- Macro files, encrypted files, external link formulas or超大 workbooks must explain limitations 
  and provide safe degradation plans.
```

### 1.5 Limitations

| Limitation | Description |
|------------|-------------|
| Macro files | Must explain limitations, provide safe degradation plan |
| Encrypted files | Must explain limitations, provide safe degradation plan |
| External link formulas | Must explain limitations, provide safe degradation plan |
| Very large workbooks | Must explain limitations, provide safe degradation plan |
| File read-only | Original input files must not be overwritten |

---

## 2. PDF Literature Reading Capability

### 2.1 Status: ️ Partially Supported

### 2.2 Environment Dependencies

| Component | Purpose | Location |
|-----------|---------|----------|
| `pypdf` | PDF text extraction | Python dependency (via `pyproject.toml`) |

### 2.3 Usage Methods

#### Chat Attachment Upload
- User uploads PDF as chat attachment
- System reads via `_read_attachment_text()`
- Calls `_extract_pdf_text()` to extract paginated text
- Text limit: max 24,000 characters (approx. 10-15 pages)

#### Code Implementation
```python
# chat_service.py
@staticmethod
def _extract_pdf_text(source: str | bytes) -> str:
    """Extract paginated text from chat PDF, avoid injecting binary content as UTF-8 to model."""
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
        pages.append(f"[Page {page_number}]\n{text[:remaining]}")
        total_chars += len(text)
    return "\n\n".join(pages)
```

### 2.4 Limitations

| Limitation | Description |
|------------|-------------|
| Text length | Max 24,000 characters (approx. 10-15 pages) |
| Scanned PDFs | Cannot extract text (requires OCR) |
| Workspace files | PDF listed as binary file, `workspace_read_file` does not read content directly |
| Sandbox environment | Sandbox image does not pre-install `pypdf`, requires runtime installation |

### 2.5 Workspace File Handling

```python
# presets.py - _BINARY_ONLY_SUFFIXES
_BINARY_ONLY_SUFFIXES = frozenset({
    ".bam", ".cram", ".bai", ".crai", ".fastq", ".fq", ".fastq.gz", ".fq.gz",
    ".h5ad", ".h5", ".rds", ".rdata", ".loom", ".bw", ".bigwig", ".2bit",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tiff",
    ".pdf", ".db", ".sqlite",  # ← PDF is in this list
})
```

**Impact**: When reading workspace PDF via `workspace_read_file`, only metadata is returned, not content.

---

## 3. Literature Summarization Capability

### 3.1 Status: ✅ Supported

### 3.2 Literature Search Tools

#### Europe PMC Search
```yaml
# data/ai/tools/research.yaml
id: research
description: Online evidence retrieval with KEGG enrichment analysis.
platform_tools:
  - europe_pmc_search
builtin_tools:
  - omichub_run_kegg_enrichment
```

#### Tool Features
- Search Europe PMC authoritative biomedical literature
- Semantic/term hybrid reranking of titles and abstracts based on user query
- Returns title, abstract, authors, journal, year, PMID/PMCID/DOI
- Open access status and traceable links
- Read-only, does not download full text

#### Code Implementation
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
        # Returns structured literature data
```

### 3.3 Literature Summarization Workflow

1. **Search Phase**
   - Call `europe_pmc_search` to search relevant literature
   - Supports year range, open access filtering
   - Returns most relevant 5-8 papers

2. **Reading Phase**
   - Upload PDF via attachment (subject to 24,000 character limit)
   - Or understand based on abstracts

3. **Summarization Phase**
   - AI model generates summary based on search results and uploaded literature
   - Can call `parallel_subagents` to process multiple subtasks in parallel

### 3.4 Limitations

| Limitation | Description |
|------------|-------------|
| Full text access | Only searches abstracts, does not download full text |
| PDF reading | Subject to 24,000 character limit, long literature cannot be fully read |
| Literature sources | Only supports Europe PMC, does not support direct PubMed search |
| Non-biomedical | Limited capability for non-biomedical literature search |

---

## 4. Comprehensive Task Scenario Analysis

### 4.1 Scenario: Process XLSX and Generate Report

**Workflow**:
1. User uploads XLSX file
2. Import to sandbox via `datahub_import`
3. Analyze with pandas in sandbox
4. Write results to `/tmp/chat_output/`
5. Platform automatically provides download

**Capability**: ✅ Fully Supported

### 4.2 Scenario: Read PDF Literature and Summarize

**Workflow**:
1. User uploads PDF as attachment
2. System extracts text (max 24,000 characters)
3. AI understands content and generates summary

**Capability**: ️ Partially Supported (limited by text length)

### 4.3 Scenario: Search Literature and Generate Review

**Workflow**:
1. Call `europe_pmc_search` to search relevant literature
2. Understand literature content based on abstracts
3. Generate literature review

**Capability**: ✅ Supported (based on abstracts)

### 4.4 Scenario: Complete Workflow (XLSX + PDF + Literature Summary)

**Workflow**:
1. Upload XLSX data file → Sandbox analysis
2. Upload PDF literature → Text extraction (limited)
3. Search Europe PMC → Get relevant literature abstracts
4. Synthesize and generate report

**Capability**: ⚠️ Partially Supported (PDF reading is bottleneck)

---

## 5. Optimization Recommendations

### 5.1 PDF Reading Capability Enhancement

| Optimization | Recommendation |
|--------------|----------------|
| Text length limit | Increase from 24,000 to 50,000+ characters |
| Workspace PDF reading | Allow `workspace_read_file` to read PDF text content |
| Sandbox PDF library | Pre-install `pypdf` or `PyMuPDF` in sandbox image |
| OCR support | Consider adding OCR capability for scanned PDFs |

### 5.2 Literature Search Enhancement

| Optimization | Recommendation |
|--------------|----------------|
| Multi-source search | Add PubMed, arXiv and other search sources |
| Full text access | Support full text download for open access literature |
| Literature management | Add literature collection, note-taking features |

### 5.3 XLSX Processing Enhancement

| Optimization | Recommendation |
|--------------|----------------|
| Large file support | Optimize processing strategy for very large Excel files |
| Template support | Provide common analysis templates |
| Visualization | Enhance Excel data visualization capability |

---

## 6. Summary

| Task Type | Capability Status | Main Limitations |
|-----------|-------------------|------------------|
| XLSX Processing | ✅ Fully Supported | Macro/encrypted/very large files need degradation handling |
| PDF Reading | ⚠️ Partially Supported | 24,000 character limit, workspace files not read directly |
| Literature Search | ✅ Fully Supported | Only Europe PMC, only returns abstracts |
| Literature Summary | ✅ Supported | Depends on abstracts, full text reading limited |

**Core Bottleneck**: Complete PDF literature reading capability is the current biggest limitation. Recommended priorities:
1. Increase PDF text extraction length limit
2. Allow workspace PDF file text reading
3. Pre-install PDF processing libraries in sandbox environment
