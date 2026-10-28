# 🧬 OmicHub 生信工具箱 · 序列与格式处理模块开发提示词

> **目标**：在现有「生信工具箱」中新增三大纯文本/坐标处理工具，保持与现有 6 个工具卡片（FASTQ 质控、BLAST、火山图、KEGG 等）一致的视觉风格与交互逻辑。
> **风格定位**：活泼、精准、极客感，文案拒绝生硬技术文档腔。

---

## 一、模块总览

| 工具ID | 显示名称 | 一句话描述 | 技术特性 |
|--------|----------|------------|----------|
| `seq_manipulator` | 🧬 序列魔术师 | DNA/RNA 反向互补、六框翻译、GC 含量，秒级纯文本运算 | 纯前端 + WebAssembly 可选 |
| `format_converter` | 🔄 格式轻量转换器 | GFF/GTF↔BED、FASTA 序列提取，常见格式一键互转 | 纯前端处理大文件流式解析 |
| `liftover` | 🗺️ LiftOver 坐标转换 | 跨版本基因组坐标映射（水稻、生菜、人类等），BED/VCF 无痛迁移 | 后端 API + 预置链文件 |

---

## 二、🧬 序列魔术师 (Sequence Manipulator)

### 2.1 功能清单

**输入区**：
- 大文本框粘贴序列（支持 FASTA 格式自动解析，自动去除 `>` 标题行）
- 序列类型自动检测：DNA / RNA / Protein（检测规则：含 U 且无 T 为 RNA；含除 ATGCU 外字母为 Protein）
- 快捷按钮：「清除」、「示例序列（水稻 ACTB 基因片段）」、「复制结果」

**操作按钮组**（图标 + 文字，横向排列，可点击后下方展开结果）：
1. **反向互补** 🔄 → 输出反向互补序列（DNA: T↔A, C↔G; RNA: U↔A）
2. **DNA → RNA** 📝 → T 替换为 U
3. **RNA → DNA** 📝 → U 替换为 T
4. **六框翻译** 🧮 → 输出 6 个阅读框的氨基酸序列（标准密码子表，支持简并密码子显示）
5. **GC 含量** 📊 → 显示 GC%、AT%、长度、N50（连续最长 ATGC 片段）、分子量估算
6. **序列清理** 🧹 → 去除数字、空格、换行，纯碱基/氨基酸序列

**结果区**：
- 只读文本框，带行号（每 60 个碱基/氨基酸换行，符合 FASTA 标准）
- 支持一键复制、下载为 `.txt` 或 `.fasta`
- 氨基酸序列使用颜色编码（疏水性/亲水性/极性/带电，参考 IGV 配色逻辑）

### 2.2 前端交互设计 (React + Arco Design)

```tsx
// 页面结构参考现有工具箱卡片，点击进入独立页面
<SeqManipulatorPage>
  {/* 顶部标题区 */}
  <PageHeader 
    title="🧬 序列魔术师" 
    subtitle="纯本地运算，你的序列不会离开浏览器，隐私绝对安全 ✨"
  />

  {/* 双栏布局：左输入，右结果 */}
  <SplitPane defaultSplit={50}>
    <LeftPanel>
      <TextArea 
        placeholder="粘贴你的序列 here... 支持 FASTA 格式"
        autoSize={{ minRows: 12, maxRows: 20 }}
        showWordCount // 显示碱基/氨基酸计数
      />
      <ButtonGroup>
        <Button icon={<IconRefresh />} onClick={reverseComplement}>反向互补</Button>
        <Button icon={<IconSwap />} onClick={dnaToRna}>DNA→RNA</Button>
        <Button icon={<IconSwap />} onClick={rnaToDna}>RNA→DNA</Button>
        <Button icon={<IconCalculator />} onClick={sixFrameTranslate}>六框翻译</Button>
        <Button icon={<IconBarChart />} onClick={gcContent}>GC 分析</Button>
        <Button icon={<IconBrush />} onClick={cleanSeq}>序列清理</Button>
      </ButtonGroup>
    </LeftPanel>

    <RightPanel>
      <ResultCard title="运算结果" extra={<CopyButton /><DownloadButton />}>
        <SequenceDisplay 
          sequence={result}
          lineLength={60}
          colorCoding={isProtein} // 蛋白质时启用氨基酸颜色
        />
      </ResultCard>

      {/* GC 分析时的统计卡片 */}
      {gcStats && (
        <StatGrid>
          <StatCard label="GC 含量" value={`${gcStats.gc}%`} color="#00b42a" />
          <StatCard label="AT 含量" value={`${gcStats.at}%`} color="#165dff" />
          <StatCard label="序列长度" value={gcStats.length} color="#86909c" />
          <StatCard label="分子量" value={`${gcStats.mw} kDa`} color="#ff7d00" />
        </StatGrid>
      )}
    </RightPanel>
  </SplitPane>
</SeqManipulatorPage>
```

### 2.3 核心算法逻辑（纯 JS/TS，无需后端）

```typescript
// 反向互补
const complement: Record<string, string> = { A: 'T', T: 'A', G: 'C', C: 'G', U: 'A', N: 'N' };
const reverseComplement = (seq: string) => 
  seq.toUpperCase().split('').reverse().map(b => complement[b] || b).join('');

// 六框翻译：+1, +2, +3, -1, -2, -3
const codonTable = { /* 标准密码子表 */ };
const translateFrame = (seq: string, frame: number) => {
  const sub = frame > 0 ? seq.slice(frame - 1) : reverseComplement(seq).slice(Math.abs(frame) - 1);
  let protein = '';
  for (let i = 0; i < sub.length - 2; i += 3) {
    const codon = sub.slice(i, i + 3);
    protein += codonTable[codon] || 'X';
  }
  return protein;
};

// GC 含量 + 分子量估算
const analyzeGC = (seq: string) => {
  const s = seq.toUpperCase().replace(/[^ATGCU]/g, '');
  const gc = (s.match(/[GC]/g) || []).length / s.length * 100;
  const mw = s.length * 330 / 1000; // 粗略估算
  return { gc: gc.toFixed(2), at: (100 - gc).toFixed(2), length: s.length, mw: mw.toFixed(2) };
};
```

### 2.4 文案风格（参考平台调性）

- 空状态：「把你的序列丢进来，我帮你变魔术 🪄」
- 运算中：「正在碱基配对中...」
- 结果提示：「搞定！共处理 ${n} 个碱基，耗时 ${ms}ms（比泡一杯咖啡还快）」
- 错误提示：「这看起来不像 DNA/RNA 序列诶，检查一下是不是混入了奇怪字符？」

---

## 三、🔄 格式轻量转换器 (Format Converter)

### 3.1 功能清单

**转换模式选择器**（Tab 切换）：
1. **GFF ↔ GTF ↔ BED** 🗂️
   - 上传/粘贴 GFF3/GTF 内容
   - 选择目标格式（BED3/BED6/BED12/GFF3/GTF）
   - 可选：仅提取特定 feature type（gene, exon, CDS, mRNA）
   - 输出：转换后的文本，支持下载

2. **FASTA 序列提取** 🎯
   - 上传 FASTA 文件（支持大文件，前端流式解析）
   - 粘贴 ID 列表（每行一个 ID，支持正则匹配）
   - 选项：保留/去除提取的序列、提取互补链、输出为 FASTA/表格

3. **ID 映射表生成** 📋
   - 输入两列 TSV/CSV（如：Transcript ID → Gene ID）
   - 输出映射字典，支持下载为 JSON/TSV

### 3.2 前端交互设计

```tsx
<FormatConverterPage>
  <PageHeader 
    title="🔄 格式轻量转换器" 
    subtitle="生信格式界的万能翻译官，拒绝格式不兼容的焦虑 😎"
  />

  <Tabs type="rounded" activeTab={mode}>
    <TabPane key="gff" title="GFF/GTF/BED 互转">
      <ConversionPanel>
        <UploadOrTextarea 
          accept=".gff,.gff3,.gtf,.bed"
          placeholder="粘贴 GFF/GTF/BED 内容，或拖拽文件..."
        />
        <ConversionSettings>
          <Select label="源格式" options={['GFF3', 'GTF', 'BED3', 'BED6', 'BED12']} />
          <IconArrowRight />
          <Select label="目标格式" options={['BED6', 'BED12', 'GFF3', 'GTF']} />
          <Checkbox label="仅保留特定 feature" />
          <Select label="Feature 类型" options={['all', 'gene', 'mRNA', 'exon', 'CDS']} />
        </ConversionSettings>
        <ConvertButton>开始转换</ConvertButton>
      </ConversionPanel>
    </TabPane>

    <TabPane key="fasta" title="FASTA 序列提取">
      <SplitPane>
        <Left>
          <UploadDragger accept=".fasta,.fa,.fna" hint="支持大文件，前端流式解析，不上传服务器" />
          <TextArea placeholder="输入 ID 列表，每行一个..." />
          <Checkbox label="允许部分匹配（如 ID 前缀）" />
          <Checkbox label="同时提取反向互补序列" />
        </Left>
        <Right>
          <ResultPreview 
            lineNumbers 
            downloadName={`extracted_${timestamp}.fasta`}
          />
          <Alert type="success" content={`成功提取 ${count} 条序列，共 ${bp} bp`} />
        </Right>
      </SplitPane>
    </TabPane>
  </Tabs>
</FormatConverterPage>
```

### 3.3 核心逻辑（前端实现）

```typescript
// GFF3 → BED6 转换
const gffToBed6 = (gffLines: string[], featureType?: string) => {
  return gffLines
    .filter(line => !line.startsWith('#') && line.trim())
    .map(line => {
      const [chrom, source, feature, start, end, score, strand, phase, attrs] = line.split('	');
      if (featureType && feature !== featureType) return null;
      const attrDict = Object.fromEntries(attrs.split(';').map(a => a.split('=')));
      const name = attrDict['Name'] || attrDict['ID'] || 'unknown';
      return `${chrom}	${+start - 1}	${end}	${name}	${score || '0'}	${strand}`;
    })
    .filter(Boolean)
    .join('
');
};

// FASTA 流式提取（使用 FileReader + 分块读取）
const extractFasta = async (file: File, idList: string[], partialMatch: boolean) => {
  const ids = new Set(idList.map(s => s.trim()).filter(Boolean));
  const results: string[] = [];
  let currentHeader = '';
  let currentSeq = '';

  // 使用 ReadableStream 处理大文件
  const reader = file.stream().getReader();
  // ... 逐行解析逻辑
};
```

### 3.4 文案风格

- 空状态：「把格式混乱的文件丢给我，还你一个清清爽爽的标准格式 ✨」
- 转换成功：「转换完成！${inputLines} 行 → ${outputLines} 行，零数据丢失」
- 错误提示：「第 ${n} 行看起来不符合 GFF3 规范，是不是漏了 tab 分隔符？」

---

## 四、🗺️ LiftOver 坐标转换

### 4.1 功能清单

**物种与版本选择**：
- 下拉选择「源参考基因组」和「目标参考基因组」
- 预置链文件（chain file）配置（YAML 驱动，支持管理员后台上传新链文件）
- 当前支持物种：水稻（v7→v8, v8→v11）、生菜（v8→v11）、人类（hg19→hg38, hg38→hg19）、小鼠（mm10→mm39）

**输入方式**：
- 粘贴 BED/VCF 内容（自动识别格式）
- 上传 BED/VCF 文件
- 支持批量转换（最大 10MB 文件）

**输出与结果**：
- 转换成功：新坐标 BED/VCF + 映射质量评分（MAPQ）
- 转换失败：未映射区域列表，标注失败原因（如坐标在目标基因组中无对应）
- 支持下载转换后文件 + 映射报告（JSON 格式）

### 4.2 前端交互设计

```tsx
<LiftOverPage>
  <PageHeader 
    title="🗺️ LiftOver 坐标转换" 
    subtitle="跨版本基因组坐标的时空传送门，让旧数据在新基因组上重获新生 🚀"
  />

  <Card className="settings-card">
    <Form layout="horizontal">
      <FormItem label="源基因组">
        <Select placeholder="从哪个版本出发？">
          <Option value="rice_v7">水稻 MSU7 (v7)</Option>
          <Option value="rice_v8">水稻 RAPDB (v8)</Option>
          <Option value="lettuce_v8">生菜 v8</Option>
          <Option value="lettuce_v11">生菜 v11</Option>
          <Option value="hg19">人类 hg19</Option>
          <Option value="hg38">人类 hg38</Option>
        </Select>
      </FormItem>

      <IconArrowRight className="arrow-icon" />

      <FormItem label="目标基因组">
        <Select placeholder="要去哪个版本？">
          {/* 动态过滤：与源版本不同物种或不同版本 */}
        </Select>
      </FormItem>

      <FormItem label="输入格式">
        <RadioGroup options={['BED', 'VCF']} />
      </FormItem>
    </Form>
  </Card>

  <UploadOrTextarea 
    placeholder="粘贴 BED/VCF 坐标... 示例：chr1  1000  2000  gene1  .  +"
    accept=".bed,.vcf,.gz"
  />

  <Button type="primary" size="large" icon={<IconRocket />}>
    启动坐标传送
  </Button>

  {/* 结果区 */}
  {result && (
    <ResultSection>
      <StatisticRow>
        <Statistic title="成功映射" value={result.mapped} suffix={`/${result.total}`} />
        <Statistic title="映射率" value={`${result.rate}%`} precision={2} />
        <Statistic title="多对一映射" value={result.multiple} />
        <Statistic title="未映射" value={result.unmapped} />
      </StatisticRow>

      <Table 
        data={result.preview}
        columns={[
          { title: '原始坐标', dataIndex: 'original' },
          { title: '新坐标', dataIndex: 'converted' },
          { title: '链方向', dataIndex: 'strand' },
          { title: '质量', dataIndex: 'score', render: (v) => <Tag color={v > 0.9 ? 'green' : 'orange'}>{v}</Tag> }
        ]}
      />

      <ButtonGroup>
        <Button icon={<IconDownload />}>下载转换结果</Button>
        <Button icon={<IconDownload />}>下载未映射列表</Button>
        <Button icon={<IconDownload />}>下载完整报告 (JSON)</Button>
      </ButtonGroup>
    </ResultSection>
  )}
</LiftOverPage>
```

### 4.3 后端 API 设计

```yaml
# API 端点
POST /api/v1/tools/liftover/convert
Request:
  source_genome: string  # 源基因组 ID
  target_genome: string  # 目标基因组 ID
  format: enum(bed, vcf)
  content: string        # 文件内容或 base64

Response:
  success: boolean
  data:
    mapped_count: int
    unmapped_count: int
    multiple_count: int
    total_count: int
    mapping_rate: float
    preview: List[MappedRecord]
    download_url: string  # 结果文件下载链接
    report_url: string    # JSON 报告下载链接
```

```python
# 后端伪代码（Python + ucsc-liftover 或 pyliftover）
from pyliftover import LiftOver
from fastapi import APIRouter, UploadFile

@router.post("/convert")
async def liftover_convert(
    source: str, 
    target: str, 
    file: UploadFile,
    format: Literal["bed", "vcf"]
):
    # 1. 根据 source_target 组合查找链文件路径
    chain_path = CHAIN_FILE_MAP[f"{source}_to_{target}"]
    lo = LiftOver(chain_path)

    # 2. 解析输入
    records = parse_bed_or_vcf(await file.read())

    # 3. 逐条转换
    results = []
    for rec in records:
        converted = lo.convert_coordinate(rec.chrom, rec.start, rec.strand)
        if converted:
            results.append({
                "original": f"{rec.chrom}:{rec.start}-{rec.end}",
                "converted": f"{converted[0][0]}:{converted[0][1]}-{converted[0][1] + rec.length}",
                "strand": converted[0][2],
                "score": len(converted)  # 映射次数，1 为最佳
            })
        else:
            results.append({"original": ..., "status": "unmapped"})

    # 4. 生成文件并返回下载链接
    return {"data": results, "download_url": generate_download(results)}
```

### 4.4 YAML 配置（链文件管理）

```yaml
# /config/tools/liftover.yaml
liftover:
  enabled: true
  icon: "🗺️"
  title: "LiftOver 坐标转换"
  description: "跨版本基因组坐标映射转换，支持 BED/VCF 格式"

  # 链文件仓库（管理员可后台上传）
  chain_files_dir: "/data/omichub/chain_files"

  # 支持的基因组映射对
  supported_pairs:
    - id: "rice_v7_to_v8"
      source: "rice_v7"
      source_label: "水稻 MSU7 (v7)"
      target: "rice_v8"
      target_label: "水稻 RAPDB (v8)"
      chain_file: "rice_v7ToV8.over.chain.gz"

    - id: "rice_v8_to_v11"
      source: "rice_v8"
      source_label: "水稻 RAPDB (v8)"
      target: "rice_v11"
      target_label: "水稻 T2T (v11)"
      chain_file: "rice_v8ToV11.over.chain.gz"

    - id: "lettuce_v8_to_v11"
      source: "lettuce_v8"
      source_label: "生菜 v8"
      target: "lettuce_v11"
      target_label: "生菜 v11"
      chain_file: "lettuce_v8ToV11.over.chain.gz"

    - id: "hg19_to_hg38"
      source: "hg19"
      source_label: "人类 hg19 (GRCh37)"
      target: "hg38"
      target_label: "人类 hg38 (GRCh38)"
      chain_file: "hg19ToHg38.over.chain.gz"

    - id: "hg38_to_hg19"
      source: "hg38"
      source_label: "人类 hg38 (GRCh38)"
      target: "hg19"
      target_label: "人类 hg19 (GRCh37)"
      chain_file: "hg38ToHg19.over.chain.gz"

  # 限制
  max_file_size: "10MB"
  max_records_per_request: 50000

  # 前端展示
  ui:
    input_placeholder: "粘贴 BED/VCF 坐标，或上传文件..."
    result_columns: ["original", "converted", "strand", "score"]
    show_mapping_stats: true
    allow_download_unmapped: true
```

### 4.5 文案风格

- 空状态：「选择基因组版本，输入坐标，我帮你穿越时空 🚀」
- 转换中：「正在解析链文件... 坐标映射中...」
- 成功：「坐标传送完成！${mapped}/${total} 成功着陆，映射率 ${rate}%」
- 未映射提示：「${n} 个坐标在目标基因组中找不到家，可能是版本间差异太大，建议手动检查」
- 错误：「源基因组和目标基因组不能是同一个版本哦，那样就不需要传送门啦 😅」

---

## 五、工具箱卡片集成配置

在现有工具箱页面中，新增三个卡片，YAML 配置如下：

```yaml
# /config/tools/toolbox.yaml
tools:
  # ... 现有 6 个工具配置 ...

  - id: "seq_manipulator"
    meta:
      icon: "🧬"
      title: "序列魔术师"
      subtitle: "反向互补、六框翻译、GC 分析，纯本地运算"
      route: "/tools/seq-manipulator"
      badge: "纯前端"
      badge_color: "arcoblue"

  - id: "format_converter"
    meta:
      icon: "🔄"
      title: "格式轻量转换器"
      subtitle: "GFF/GTF/BED 互转、FASTA 序列提取"
      route: "/tools/format-converter"
      badge: "零上传"
      badge_color: "green"

  - id: "liftover"
    meta:
      icon: "🗺️"
      title: "LiftOver 坐标转换"
      subtitle: "跨版本基因组坐标映射，支持多物种"
      route: "/tools/liftover"
      badge: "生产级"
      badge_color: "orange"
```

### 前端卡片渲染逻辑（与现有工具一致）

```tsx
// ToolCard 组件复用现有样式
<ToolCard
  icon={tool.meta.icon}
  title={tool.meta.title}
  subtitle={tool.meta.subtitle}
  badge={tool.meta.badge}
  badgeColor={tool.meta.badge_color}
  onClick={() => navigate(tool.meta.route)}
/>
```

---

## 六、开发排期建议

| 阶段 | 内容 | 预估工时 | 负责人 |
|------|------|----------|--------|
| **Phase 1** | 序列魔术师（纯前端，零后端依赖） | 1-2 天 | 前端 |
| **Phase 2** | 格式轻量转换器（纯前端，大文件流式解析） | 2-3 天 | 前端 |
| **Phase 3** | LiftOver 后端 API + 链文件管理 | 3-4 天 | 后端 |
| **Phase 4** | 集成测试 + 文案调优 + 工具箱卡片接入 | 1 天 | 前后端联调 |

---

## 七、给 CC 的优化提示词（可直接复制）

```
请基于以下要求优化 OmicHub 生信工具箱的三个新工具：

1. 序列魔术师：
   - 使用 React + Arco Design 实现双栏布局（左输入右结果）
   - 所有运算纯前端完成，使用 TypeScript 实现反向互补、六框翻译、GC 分析
   - 蛋白质序列显示使用氨基酸颜色编码（疏水性蓝色、亲水性红色、极性绿色、带电黄色）
   - 文案风格活泼，空状态提示使用 emoji 装饰

2. 格式轻量转换器：
   - 使用 Tabs 切换 GFF/GTF/BED 互转和 FASTA 提取两个模式
   - FASTA 提取支持大文件（>100MB）前端流式解析，使用 FileReader + 分块读取
   - 转换结果带行号预览，支持一键复制和下载

3. LiftOver 坐标转换：
   - 后端使用 Python + pyliftover 或 ucsc-liftover 实现
   - 链文件通过 YAML 配置管理，支持管理员后台上传
   - 前端展示映射统计卡片（成功率、映射率、多对一数量）
   - 支持下载转换结果、未映射列表、JSON 报告三种格式

4. 统一要求：
   - 三个工具都需要在工具箱首页以卡片形式展示，与现有 6 个工具风格一致
   - 所有页面需要适配暗黑模式
   - 响应式布局，支持移动端基础操作
   - 添加路由：/tools/seq-manipulator, /tools/format-converter, /tools/liftover
```

---

*文档生成时间：2026-07-06*
*版本：v1.0 - 初版完整方案*
