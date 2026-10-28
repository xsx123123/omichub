# bio-rna-quantification-count-matrix-qc

> Bundled component reference for `rna-quantification/count-matrix-qc` (original source: `skills/bio_skills/rna-quantification/count-matrix-qc`).

Quality control and exploration of RNA-seq count matrices before differential expression. Use when checking library sizes and composition, choosing VST vs rlog for visualization, running PCA and sample correlation, detecting outliers with Cook's distance, deciding how to handle known vs unknown batch effects, screening for sample swaps, or judging whether a sample or design is too compromised to test.

## Instructions

## Version Compatibility

Reference examples tested with: DESeq2 1.42+, edgeR 4.0+, ggplot2 3.5+, pheatmap 1.0+, matplotlib 3.8+, numpy 1.26+, pandas 2.2+, scikit-learn 1.4+, scipy 1.12+, seaborn 0.13+

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Count Matrix QC

**"Check my count matrix for outliers and batch effects"** -> Assess depth, composition, sample relationships, and outliers on appropriately transformed data, then decide what (if anything) to remove or model before differential expression.
- R: `DESeq2::vst()` -> `plotPCA()`, sample-distance heatmap, Cook's distance
- Python: `sklearn.decomposition.PCA`, `seaborn.clustermap` (with the low-count caveat below)

Two principles govern this whole skill. First, DE testing runs on raw counts with a size-factor offset; the transformed matrices here are for QC and visualization only, never fed back into the count model. Second, raw counts confound depth, composition, and biology, so QC must look at the right scale: a variance-stabilized matrix for clustering/PCA, and the size factors and Cook's distances from the count model for normalization and outliers.

## Load and Inspect

**Goal:** Get counts into a model object and read off depth and detection per sample.

**Approach:** Build a DESeqDataSet (from tximport or a matrix), then summarize library size and genes detected.

```r
library(DESeq2)
counts <- read.csv('count_matrix.csv', row.names = 1)
coldata <- data.frame(condition = factor(c('ctrl', 'ctrl', 'treat', 'treat')),
                      row.names = colnames(counts))
dds <- DESeqDataSetFromMatrix(countData = counts, colData = coldata, design = ~ condition)

colSums(counts(dds))        # library size per sample
colSums(counts(dds) > 0)    # genes detected per sample
```

```python
import pandas as pd, numpy as np
counts = pd.read_csv('count_matrix.csv', index_col=0)
metadata = pd.read_csv('sample_info.csv', index_col=0)
print(counts.sum()); print((counts > 0).sum())
```

## Filtering: the principled cut

**Goal:** Drop genes with too little signal to test, in a depth- and design-aware way.

**Approach:** Prefer edgeR `filterByExpr` (keeps genes with enough counts in at least the smallest group's worth of samples) over an arbitrary `CPM > 1` rule.

```r
library(edgeR)
keep <- filterByExpr(counts(dds), group = dds$condition)
dds <- dds[keep, ]
```

```python
min_counts, min_samples = 10, 3   # 10 reads in >=3 samples; ~smallest group size
counts_filt = counts[(counts >= min_counts).sum(axis=1) >= min_samples]
```

In DESeq2, pre-filtering is mainly for speed and to drop all-zero rows; the inferential filter is independent filtering done automatically inside `results()` (it picks a mean-count threshold maximizing discoveries at the chosen alpha). Keep pre-filtering light. For edgeR/limma-voom, `filterByExpr` is the filter.

## Normalization and transformation

Composition bias is the reason depth scaling is not enough: if a few genes dominate a library, every other gene looks depressed at unchanged absolute output. DESeq2 median-of-ratios and edgeR TMM each estimate one size factor per sample assuming most genes are not DE, then apply it as an offset on the raw counts. CPM and TPM do NOT correct composition (they rescale by a within-sample total) -- the same reason TPM is invalid for cross-sample comparison upstream -- so they are for visualization, not DE normalization. For matrices with many structural zeros (single-cell, metagenomics), use the `poscounts` size-factor estimator.

For QC visualization the matrix must be homoskedastic. `log2(CPM + 1)` is not: at low counts the log amplifies sampling noise, so PCA on it is driven by noisy near-zero genes. Use a variance-stabilizing transform instead.

| Transform | Speed | Use when |
|-----------|-------|----------|
| `vst()` | Fast | Default, especially medium-to-large n (>30) |
| `rlog()` | Slow | Small n (roughly < 30) and heterogeneous designs; but can over-shrink when size factors span a very wide range (then prefer vst) |

```r
vsd <- vst(dds, blind = TRUE)    # blind=TRUE for unsupervised QC; FALSE only after DESeq() for plotting
mat <- assay(vsd)
```

## PCA and sample relationships

**Goal:** See whether replicates cluster and whether PC1 is biology or a technical artifact.

**Approach:** PCA on the VST matrix (top variable genes), then read PC1 against depth and batch.

```r
plotPCA(vsd, intgroup = 'condition')                     # uses top 500 most-variable genes
sampleDists <- dist(t(assay(vsd)))
pheatmap::pheatmap(as.matrix(sampleDists))
```

```python
from sklearn.decomposition import PCA
# log-CPM PCA is a quick look only: low-count heteroskedasticity can drive the PCs.
# For publication QC, compute VST in R and bring the matrix into Python.
cpm = counts_filt * 1e6 / counts_filt.sum()
log_cpm = np.log2(cpm + 1)
pcs = PCA(n_components=2).fit_transform(log_cpm.T)
```

If PC1 correlates with library size or detected-gene count rather than condition, it is a depth artifact (color the PCA by `log10` library size to confirm). A common pattern is PC1 = batch, PC2 = condition, which is a design problem, not a normalization fix.

## Outlier detection with Cook's distance

**Goal:** Distinguish a single bad count in one gene from a globally bad sample.

**Approach:** Read per-gene-per-sample Cook's distances from the fitted model; treat single-gene outliers and whole-sample outliers differently.

```r
dds <- DESeq(dds)
cooks <- assays(dds)[['cooks']]          # per gene x sample; NOT results(dds)$cooksd
boxplot(log10(cooks), las = 2, main = "Cook's distance")
# results() flags a gene whose max Cook's exceeds qf(0.99, p, m-p) by setting its p-value to NA.
# With >= 7 replicates per group (minReplicatesForReplace) DESeq2 replaces the outlier count instead.
```

A single-gene-in-one-sample outlier is exactly what Cook's filtering and `replaceOutliers` are for; let DESeq2 handle it. A whole-sample outlier (many flagged genes in one sample, that sample far on the VST-PCA, low correlation to its replicates, an anomalous size factor) is not rescuable by `replaceOutliers`. Investigate, and remove only with a documented technical cause, since post-hoc cherry-picking inflates false positives.

## Batch effects

Known batch goes in the design; the engine estimates and removes it on raw counts while propagating uncertainty:

```r
design(dds) <- ~ batch + condition       # condition last = contrast of interest
```

Do NOT run `removeBatchEffect()` or ComBat and feed the adjusted matrix into DESeq2/edgeR; those engines model batch internally, and pre-adjusting double-corrects and breaks the count model. `limma::removeBatchEffect(assay(vsd), batch = vsd$batch)` is for visualization only. For unknown/unmeasured structure, estimate surrogate variables (`sva`/`svaseq`) or factors of unwanted variation (`RUVSeq`: RUVg control genes, RUVs replicate samples, RUVr residuals) and add them to the design.

The fatal case: if batch is correlated with condition, regressing it out removes biology too; a perfect confound (all treated in batch 1, all control in batch 2) is statistically unfixable. Cross-tabulate batch against condition before fitting.

## Library-level QC and sample swaps

```r
sf <- sizeFactors(estimateSizeFactors(dds))   # a size factor far from 1 (< ~0.3 or > ~3) is a red flag
```

Do not deduplicate standard RNA-seq: high duplication is expected from highly expressed genes, and position-based dedup discards real signal (deduplicate only with UMIs). Screen for sample swaps cheaply with sex-linked genes (XIST high in XX; RPS4Y1/UTY/DDX3Y high in XY) against recorded sex, and confirm identity with genotype concordance tools (VerifyBamID, somalier) when available.

## Red flags that should halt a DE analysis

1. A sample clusters away from its group on the VST-PCA (and concentrates Cook's-flagged genes).
2. A size factor far from 1, or a library an order of magnitude off the cohort.
3. Near-zero correlation of a sample to its replicates.
4. Condition (near-)perfectly confounded with batch, lane, or run.

## Common Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `results(dds)$cooksd` is NULL | Cook's distance is not a results column | Read `assays(dds)[['cooks']]` |
| PCA driven by a few noisy genes | PCA run on `log2(CPM+1)` or raw counts | Use VST/rlog; restrict to top-variable genes |
| Batch effect persists after correction | `removeBatchEffect` output fed to DESeq2 | Put batch in the design instead; keep correction for plots only |
| Every gene significant, or none | Sample swap / confounded batch / wrong normalization | Check metadata, batch x condition table, and size factors first |
| One transform behaves oddly with wide size factors | rlog over-shrinks | Switch to vst |

## Related Skills

- rna-quantification/featurecounts-counting - Generate the count matrix
- rna-quantification/tximport-workflow - Import transcript counts with the length offset
- differential-expression/deseq2-basics - DE testing after QC
- differential-expression/de-visualization - Downstream result visualization
- read-qc/rnaseq-qc - Upstream read-level QC (rRNA, degradation, contamination)

## References

- Love MI, Huber W, Anders S. 2014. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. Genome Biol 15(12):550. doi:10.1186/s13059-014-0550-8
- Robinson MD, Oshlack A. 2010. A scaling normalization method for differential expression analysis of RNA-seq data. Genome Biol 11(3):R25. doi:10.1186/gb-2010-11-3-r25
- Risso D, Ngai J, Speed TP, Dudoit S. 2014. Normalization of RNA-seq data using factor analysis of control genes or samples. Nat Biotechnol 32(9):896-902. doi:10.1038/nbt.2931

## Usage Guide

# Count Matrix QC - Usage Guide

## Overview
Quality control of count matrices is essential before differential expression analysis to identify outliers, batch effects, and sample quality issues.

## Prerequisites
```r
if (!require('BiocManager', quietly = TRUE))
    install.packages('BiocManager')

BiocManager::install('DESeq2')
install.packages('pheatmap')
```

## Quick Start
Tell your AI agent what you want to do:
- "Check the quality of my count matrix before DE analysis"
- "Identify outlier samples in my RNA-seq data"
- "Make a PCA plot to see if my samples cluster by condition"

## Example Prompts
### Basic QC
> "Run QC on my count matrix and identify any problematic samples"

> "Check library sizes and gene detection rates across my samples"

### Visualization
> "Create a sample correlation heatmap from my count data"

> "Make a PCA plot colored by condition and batch"

### Outlier Detection
> "Check if any samples are outliers based on PCA and correlation"

> "Should I remove sample X based on the QC metrics?"

### Batch Effects
> "Check if my samples show batch effects in PCA"

> "Add batch correction to my DESeq2 design"

## What the Agent Will Do
1. Load the count matrix and sample metadata
2. Calculate library sizes and gene detection rates
3. Normalize counts for visualization (VST or rlog)
4. Generate sample correlation heatmap
5. Create PCA plot to assess sample clustering
6. Identify any outliers or batch effects
7. Recommend next steps based on QC results

## Key QC Checks

1. **Library sizes** - Total counts per sample
2. **Gene detection** - Number of genes with counts
3. **Sample correlation** - Replicates should cluster together
4. **PCA** - Samples should separate by condition, not batch
5. **Outlier detection** - Identify problematic samples

## Quick QC in R

```r
library(DESeq2)
library(pheatmap)

# Load data
dds <- DESeqDataSetFromMatrix(countData = counts, colData = coldata,
                              design = ~ condition)

# Filter low counts
dds <- dds[rowSums(counts(dds)) >= 10, ]

# Normalize
vsd <- vst(dds, blind = TRUE)

# Sample correlation
pheatmap(cor(assay(vsd)))

# PCA
plotPCA(vsd, intgroup = 'condition')
```

## What to Look For

### Good Signs
- Replicates cluster together in PCA
- High correlation (>0.9) between replicates
- Similar library sizes across samples
- Clear separation between conditions

### Warning Signs
- Sample doesn't cluster with its group
- Low correlation with replicates
- Very different library size
- PCA driven by batch, not condition

## Handling Problems

### Outlier Samples
```r
# Option 1: Remove outlier
dds <- dds[, colnames(dds) != 'outlier_sample']

# Option 2: Flag for sensitivity analysis
# Run with and without outlier
```

### Batch Effects
```r
# Known batch: put it in the design (never pre-correct counts for DESeq2/edgeR)
design(dds) <- ~ batch + condition
```
- removeBatchEffect/ComBat output is for visualization only; feeding it to the count model double-corrects.
- Unknown batch: estimate surrogate variables (sva/svaseq) or factors of unwanted variation (RUVSeq) and add to the design.
- Confounding is fatal: if batch tracks condition, regressing it out removes biology too. Cross-tabulate batch against condition first; a perfect confound is unfixable.

### Sample Swaps
- Check sex genes (XIST for XX; RPS4Y1/UTY/DDX3Y for XY) against recorded sex; a mismatch is a swap until proven otherwise.

### Low Library Size
- Consider excluding samples with very low depth, but document the reason.
- Do not deduplicate standard RNA-seq (high duplication is expected); deduplicate only with UMIs.

## Recommended Thresholds

| Metric | Good | Concerning |
|--------|------|------------|
| Library size | >5M | <1M |
| Genes detected (human poly-A bulk) | >12,000 | <8,000 |
| Replicate correlation | >0.95 | <0.85 |
| Mapping rate (upstream quant check) | >70% | <50% |

Gene-detection numbers are organism-, tissue-, and protocol-specific; the values above are typical for human poly-A bulk RNA-seq. Calibrate against the cohort rather than treating them as universal cutoffs.

## Tips
- Always run QC before differential expression analysis
- Use blind=TRUE for vst/rlog when doing unsupervised QC
- Document any samples removed and justify the decision
- Run sensitivity analysis if unsure about removing a sample
- Check for batch effects even if not explicitly part of the design

## Bundled Files

- `rna-quantification--count-matrix-qc--examples--qc_analysis.py` — copied from `examples/qc_analysis.py`
- `rna-quantification--count-matrix-qc--examples--qc_report.R` — copied from `examples/qc_report.R`
