# bio-chipseq-differential-binding

> Bundled component reference for `chip-seq/differential-binding` (original source: `skills/bio_skills/chip-seq/differential-binding`).

Identifies differentially bound ChIP-seq regions between conditions using DiffBind, csaw (sliding windows), DESeq2/edgeR/PyDESeq2 on count matrices, NormR (control-aware), or MAnorm2. Distinguishes three distinct normalization problems (composition bias, trended bias, global shifts) and matches each to its appropriate fix including spike-in scaling. Use when comparing ChIP-seq binding between experimental conditions, choosing normalization for global vs local changes, integrating spike-in data, or reconciling DiffBind/DESeq2 disagreement.

## Instructions

## Version Compatibility

Reference examples tested with: DiffBind 3.20+, DESeq2 1.42+, edgeR 4.0+, csaw 1.36+, PyDESeq2 0.5+, NormR 1.28+, MAnorm2 1.2+, ChIPseqSpikeInFree 1.6+.

DiffBind 3.0+ changed defaults: `summits=200` (was FALSE), `dba.normalize()` now required, blacklist filtering on by default, full library size normalization replaces reads-in-peaks. Always run `packageVersion('DiffBind')` and inspect `dba.normalize(obj, bRetrieve=TRUE)` to confirm what was applied.

# Differential ChIP-seq Binding

**"Compare protein-DNA binding between experimental conditions"** -> Identify regions where IP signal changes significantly, accounting for sequencing depth, composition bias, trended biases, and global shifts that confound naive normalization.

- R (BAM + peaks): `DiffBind::dba()` -> `dba.count()` -> `dba.normalize()` -> `dba.analyze()`
- R (count matrix): `DESeq2::DESeq()` or `edgeR::glmQLFTest()` on a peaks-by-samples matrix
- R (windows-based, global-shift-robust): `csaw::windowCounts()` -> `csaw::normFactors()` -> `edgeR::glmQLFTest()`
- R (control-aware): `normr::diffR(chip1.bam, chip2.bam, genome)` joint binomial mixture
- Python (count matrix): `pydeseq2.DeseqDataSet()`

Choice of normalization matters more than choice of test statistic (RLE vs TMM vs csaw bin-TMM on the same reference reads produce nearly identical results). Choose by which of the three normalization problems applies.

## The Three Distinct Normalization Problems

| Problem | Symptom on MA plot | Cause | Fix |
|---------|--------------------|-------|-----|
| **Composition bias** | Loess shifts off y=0 systematically | Few high-signal peaks dominate read counts; small fold changes look large or inverted | TMM on background 10 kb bins (csaw / DiffBind `background=TRUE`); NOT reads-in-peaks |
| **Trended bias (intensity-dependent)** | Loess curve sweeps from + to - across abundance | Library-prep efficiency varies with fragment abundance | Non-linear loess offsets (csaw `normOffsets`); use cautiously — can over-normalize biology |
| **Global shift (treatment changes most peaks)** | Loess entirely shifted off y=0; mean log2FC ≠ 0 | Drug/perturbation changes the genome-wide level of binding (HDACi, BETi, EZH2i, target KD) | Spike-in scaling (ChIP-Rx); no algorithmic fix works |

**Why this matters:** Most published ChIP-seq differential analyses default to RLE/TMM on reads-in-peaks, which assumes "most peaks are unchanged." For HDAC inhibitors, BET inhibitors, EZH2 inhibitors, or any large dosage / target-knockdown experiment, this assumption is violated. The algorithm forces the median log2FC to zero, hides the real effect, and amplifies noise around the new "zero." The result can have the wrong sign.

**Diagnostic:** Plot MA loess on differential results. A loess curve that sweeps abundance indicates trended bias. A uniformly shifted loess indicates a global shift. Both patterns together indicate normalization is failing in two ways simultaneously.

## Algorithmic Taxonomy

| Tool | Treats | Statistical model | Strength | Fails when |
|------|--------|-------------------|----------|------------|
| **DiffBind 3.20+** | Consensus peaks summit ± 200 bp (default) | DESeq2 or edgeR backend | Mature; integrated counting/normalization; spike-in support; blacklist filter on | Default `summits=200` recenters peaks (wrong for broad marks); `DBA_NORM_LIB` is conservative but misses global shifts unless `background=TRUE` |
| **DESeq2 (direct)** | Predefined peaks | NB GLM | Familiar; transparent | RLE on reads-in-peaks fails for global shifts |
| **edgeR (direct)** | Predefined peaks | NB GLM with TMM; quasi-likelihood F-test | Cleaner small-sample inference; QL-F controls type-I error | TMM on peak counts unstable if peaks globally shifting |
| **csaw** (Lun & Smyth 2016) | Sliding windows (typically 150 bp width, 50 bp shift) | edgeR QL-F | Gold-standard for global shifts; bin-TMM composition bias; loess for trended biases | Slower; requires BAMs not count matrix; window-merge step adds complexity |
| **NormR** (Helmuth 2016) | Genomic bins | Binomial mixture (background + enriched) | Control-aware; identifies enrichment/depletion/background simultaneously | Bin-level not peak-level; older codebase; less integration with downstream tools |
| **MAnorm2** (Tu 2021) | Peaks | Hierarchical model with mean-variance trend | Designed for cross-condition with replicates | Less widely adopted; sparse maintenance |
| **SpikChIP** (Blanco 2021) | Peaks | Spike-in-aware | Multi-sample spike-in comparison | Niche; specific spike-in protocol assumed |
| **SpikeFlow** (2024) | End-to-end | Snakemake pipeline: MACS2/EPIC2/EDD peaks + DESeq2 with spike-in size factors | Automated; multiple normalization options (RPM/RRPM/Rx-Input/downsampling) | Inherits experimental-design errors upstream |
| **ChIPComp** (Chen 2015) | Peaks | Joint Poisson with input | Control-aware | Older; less maintained |
| **ChIPseqSpikeInFree** (Jin 2020) | Peaks (post-hoc) | Distribution-shape inference | Detects global shift WITHOUT spike-in | Post-hoc heuristic only; not definitive; sanity check |

## Decision Tree: Choosing Normalization

| Scenario | Recommended | Tool / parameter |
|----------|-------------|------------------|
| Standard TF ChIP, local changes expected, balanced gain/loss | RLE on reads-in-peaks | DESeq2 default; DiffBind `DBA_NORM_RLE` |
| Histone marks, broad domains, local changes | TMM on background 10 kb bins | csaw `normFactors`; DiffBind `background=TRUE` |
| HDAC / BET / EZH2 inhibitor (global change) | Spike-in scaling | DiffBind `spikein=TRUE`; SpikeFlow; manual `sizeFactors()` from spike reads |
| Dosage titration, cell-cycle synchronization | Spike-in scaling | Same |
| ChIP target knockdown / degron | Spike-in or matched-input control subtraction | Spike-in preferred; bamCompare log2 ratio next |
| CUT&RUN/CUT&Tag standard | E. coli spike-in (carryover) | DiffBind custom scaling; see cut-and-run-tag |
| No spike-in available; suspect global shift | ChIPseqSpikeInFree | Post-hoc distribution-shape inference |
| Suspected trended (abundance-dependent) bias | Non-linear loess | csaw `normOffsets` |
| Genome-wide enrichment/depletion analysis | NormR | Binomial mixture |
| Many conditions, large peak set | edgeR QL-F or DiffBind+edgeR | Better type-I control than DESeq2 Wald |

## Spike-In Scaling Factor Calculation

ChIP-Rx (Orlando 2014) uses Drosophila chromatin spike-in added at fixed concentration BEFORE IP. Egan 2016 adds a fixed MASS of Drosophila S2 chromatin (matched to target chromatin by the ~27:1 human:fly genome-size ratio), not a fixed cell count.

**RRPM (reference-adjusted reads per million):**

```
scale_factor_i = min(N_spike_sample) / N_spike_sample_i
```

Apply to read counts pre-test, OR pass as `sizeFactors()` to DESeq2 / `normFactors()` to edgeR / a numeric library-size vector to DiffBind's `dba.normalize(..., library=...)`:

```r
spike_in_reads <- c(120000, 145000, 110000, 95000)  # per-sample Drosophila read count
sample_names <- c('ctrl_1', 'ctrl_2', 'treat_1', 'treat_2')
scale_factors <- min(spike_in_reads) / spike_in_reads
names(scale_factors) <- sample_names

# DESeq2 with spike-in size factors
sizeFactors(dds) <- 1 / scale_factors  # DESeq2 expects inverse convention

# Or directly via DiffBind 3.x (spikein = TRUE forces library = DBA_LIBSIZE_BACKGROUND internally)
dba_obj <- dba.normalize(dba_obj, spikein = TRUE,
                          normalize = DBA_NORM_LIB)
```

**Rx-Input variant** (Fursova 2019): additionally scale by input spike-in to correct IP efficiency variation.

**Internal-control sanity check:** After spike-in normalization, blacklist regions and constitutive housekeeping sites (U6 promoter, rRNA processing factors that are stable) should show no signal change. If they do, the normalization is broken — common causes:
- Spike-in scaling applied to peak counts instead of read counts
- Spike-in reads not deduplicated before scaling
- Spike-in genome not filtered for high-mapq before scaling
- Spike-in saturated (always 100k+ reads); check titration linearity

Per the Patel et al 2024 *Nat Biotechnol* survey, improper spike-in normalization is common: of 53 datasets examined, only 27 (~51%) had adequate matched input controls across conditions.

## DiffBind Workflow (BAMs + Peaks)

**Goal:** Run DiffBind from a sample sheet to consensus peaks, normalized counts, and tested differential binding.

**Approach:** Build sample sheet, count reads in consensus peaks (summit-centered for narrow marks, full peak width for broad), choose normalization based on the three-problem framework above, then test with DESeq2 or edgeR backend.

```r
library(DiffBind)

# Sample sheet: SampleID, Condition, Replicate, bamReads, bamControl, Peaks, PeakCaller
dba_obj <- dba(sampleSheet = 'samples.csv')

# Counting: summits=250 (narrow); FALSE for broad histones (use full peak width)
dba_obj <- dba.count(dba_obj, summits = 250, minOverlap = 2, bParallel = TRUE)

# Normalization — choose per the three-problem framework
dba_obj <- dba.normalize(dba_obj,                      # default: full library size
                          method = DBA_DESEQ2,
                          normalize = DBA_NORM_LIB,
                          library = DBA_LIBSIZE_FULL)

# Background bin TMM for composition bias / broad marks
# dba_obj <- dba.normalize(dba_obj, background = TRUE)

# Spike-in scaling for global shifts
# dba_obj <- dba.normalize(dba_obj, spikein = TRUE)

dba_obj <- dba.contrast(dba_obj, design = '~ Condition')
dba_obj <- dba.analyze(dba_obj, method = DBA_DESEQ2)

# Always inspect what was actually applied
dba.normalize(dba_obj, bRetrieve = TRUE)
```

DiffBind 3.20+ defaults (verified via `bRetrieve`):
- `summits = 200` — narrow recentering (set `FALSE` for broad histones)
- `library = DBA_LIBSIZE_FULL` — full library, conservative
- `normalize = DBA_NORM_LIB` — library size only, not reads-in-peaks RLE
- Blacklist filtering on
- `background = FALSE` — set `TRUE` for composition bias

## csaw Workflow (Windows-Based)

**Goal:** Detect differential binding from sliding windows without committing to predefined peaks; robust to composition bias via background bin TMM.

**Approach:** Count reads in overlapping windows, normalize on 10 kb bins (composition bias) and/or loess (trended bias), test with edgeR QL-F, then merge significant windows into regions.

```r
library(csaw)
library(edgeR)

bam_files <- c('ctrl_1.bam', 'ctrl_2.bam', 'treat_1.bam', 'treat_2.bam')
condition <- factor(c('ctrl', 'ctrl', 'treat', 'treat'))

# Window counts: 150 bp window, 50 bp spacing (sharp marks); 1-2 kb for broad
param <- readParam(minq = 30, pe = 'both', dedup = TRUE,
                    discard = import('hg38-blacklist.v2.bed'))
windows <- windowCounts(bam_files, width = 150, ext = 200, param = param)

# Composition bias via 10 kb bins (always applied for ChIP-seq)
bg_bins <- windowCounts(bam_files, bin = TRUE, width = 10000, param = param)
windows <- normFactors(bg_bins, se.out = windows)

# Optional: trended bias via non-linear loess (use cautiously)
# windows <- normOffsets(windows, se.out = TRUE)

# edgeR QL-F test
y <- asDGEList(windows)
design <- model.matrix(~condition)
y <- estimateDisp(y, design)
fit <- glmQLFit(y, design, robust = TRUE)
results <- glmQLFTest(fit, coef = 2)

# Merge significant windows within 1 kb into regions
merged <- mergeResults(windows, results$table, tol = 1000, merge.args = list(max.width = 5000))
```

For broad marks, increase window width to 1-2 kb and merge tolerance to 5 kb. For TFs, 150 bp window + 50 bp spacing is standard.

## DESeq2 from Count Matrix

```r
library(DESeq2)

counts <- read.delim('counts.tsv', row.names = 1, check.names = FALSE)
coldata <- data.frame(
    condition = factor(c('ctrl', 'ctrl', 'ctrl', 'treat', 'treat', 'treat')),
    row.names = colnames(counts)
)

dds <- DESeqDataSetFromMatrix(countData = counts, colData = coldata, design = ~ condition)

# Pre-filtering for ChIP-seq is LESS aggressive than RNA-seq (peaks already enriched)
keep <- rowSums(counts(dds)) >= 1  # remove only all-zero
dds <- dds[keep, ]
dds$condition <- relevel(dds$condition, ref = 'ctrl')

dds <- DESeq(dds)
res <- results(dds, alpha = 0.05)  # match independent-filtering optimization

# Optional: LFC shrinkage for ranking/visualization only — does NOT change padj
library(apeglm)
resLFC <- lfcShrink(dds, coef = 'condition_treat_vs_ctrl', type = 'apeglm')
```

For spike-in normalization, set `sizeFactors(dds)` from scaling factors before `DESeq(dds)`. For background-bin TMM (composition bias) use csaw to compute size factors, then transfer.

## Per-Tool Failure Modes

### DiffBind -- `summits=200` default destroys broad marks

**Trigger:** Default DiffBind 3.x call with histone broad marks (H3K27me3, H3K9me3).

**Mechanism:** `summits=200` re-centers peaks to summit ± 200 bp, throwing away most of a 10-100 kb broad domain.

**Symptom:** Differential count for broad marks much lower than expected; signal concentrated at narrow centers of broad regions.

**Fix:** `dba.count(obj, summits = FALSE, ...)` for broad marks; OR use full-width consensus peaks; OR switch to csaw with 1-2 kb windows.

### DiffBind -- `DBA_NORM_RLE` reads-in-peaks default reverses global shifts

**Trigger:** Default (legacy DiffBind < 3.0) OR explicitly setting `normalize = DBA_NORM_RLE` on a global-shift experiment.

**Mechanism:** RLE on reads-in-peaks assumes most peaks unchanged. If 80% of peaks lose signal (e.g., EZH2 inhibitor on H3K27me3), the size factors compensate by inflating the "lost" peaks' normalized values toward control levels.

**Symptom:** Differential results show fewer peaks changed than visually obvious; or signs are wrong (gain reported where loss occurred).

**Fix:** Switch to `background = TRUE` (bin TMM); for definitive analysis use `spikein = TRUE` with ChIP-Rx.

### DESeq2 -- Pre-filtering removes condition-specific peaks

**Trigger:** Applying RNA-seq-style filter `rowSums(counts) >= 10` to ChIP-seq counts.

**Mechanism:** A peak present in treatment but absent in control has near-zero control counts. Aggressive filtering removes truly differential peaks.

**Symptom:** Significantly differential gains-of-binding peaks missing from results.

**Fix:** `rowSums(counts) >= 1` only (remove all-zero rows); accept the loss of statistical power vs. recovering true differential peaks.

### csaw -- Trended bias loess over-normalizes biology

**Trigger:** Applying `normOffsets()` (loess) when the abundance-dependent shift IS the biology.

**Mechanism:** Loess fits a smooth curve to the MA-plot trend; if treatment uniformly increases binding at low-signal peaks (which is biology), loess interprets it as a technical trend and removes it.

**Symptom:** No differential peaks detected despite obvious treatment effect.

**Fix:** Use bin-TMM only (composition bias); apply loess only after confirming the trend is technical (e.g., it appears in IgG-only samples).

### Spike-in normalization -- Scaling factor applied to wrong layer

**Trigger:** Multiplying peak counts by spike-in scaling factor.

**Mechanism:** Spike-in factors are for read-level normalization; applied to peak counts they double-correct (peak counts already reflect mapped reads).

**Symptom:** Effect sizes shifted by 2-10× from expected biology; internal-control regions show artifactual signal change.

**Fix:** Apply spike-in via `sizeFactors(dds)` (DESeq2) or `normFactors` (edgeR) BEFORE the test; or via `bamCoverage --scaleFactor` for browser tracks. Never multiply peak-level counts.

### IDR-passing peaks not used as differential input

**Trigger:** Using per-replicate MACS calls (loose `-p 1e-2`) as DiffBind peak input.

**Mechanism:** Loose ENCODE-pattern peaks include many low-confidence calls; DiffBind's `minOverlap = 2` may not filter aggressively enough.

**Symptom:** Differential results dominated by noise at marginal peaks; high false-positive rate.

**Fix:** Pre-filter peak input to IDR-passing peaks (TF) or naive-overlap-passing peaks (histone) before DiffBind ingestion.

## Reconciliation: When Methods Disagree

| Pattern | Likely cause | Action |
|---------|--------------|--------|
| DiffBind + DESeq2 directly differ wildly | Different normalization (DiffBind default = library size; DESeq2 default = RLE) | Force same normalization; differences should shrink to <5% |
| csaw windows + DiffBind peaks disagree | csaw catches sub-peak local maxima or wider regions DiffBind missed | Inspect IGV; csaw windows-based often more sensitive to broad/diffuse changes |
| Spike-in scaled + non-scaled give opposite signs | Global shift present | Spike-in is correct; non-scaled is fooled by composition bias |
| DiffBind run twice gives different results | Different `summits` or `minOverlap` settings | Verify via `dba.normalize(obj, bRetrieve=TRUE)`; pin parameters in script |
| Few replicates, large fold changes, low padj | DESeq2 dispersion estimate unstable with n=2 | Switch to edgeR QL-F or DiffBind with edgeR backend |
| Different fold changes in DiffBind 3.x vs 2.x | Default normalization changed | Match settings explicitly; document version in methods |

**Operational rule for publication-grade:** Run on ENCODE-pattern peaks (IDR or naive overlap-passing), normalize with both reads-in-peaks AND background-bin AND spike-in if available; require concordance across at least two methods. For global-shift experiments, spike-in is mandatory.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| `Error: dba.normalize() must be called before dba.analyze()` | DiffBind 3.x change; not in older docs | Add `dba.normalize(obj)` step |
| DiffBind very slow on many samples | Sequential counting | `dba.count(obj, bParallel = TRUE)` |
| `Error in DESeq()` with few replicates | Dispersion estimation unstable | Use `DESeq(dds, fitType = 'parametric', sfType = 'poscounts')` or switch to edgeR |
| Spike-in size factors mostly NA | Spike-in reads not in sample sheet or wrong BAM path | Verify spike-in BAM exists; load via DiffBind `spikein` field |
| All padj = NA | Independent filtering too aggressive | Lower `alpha` in `results()` to match intended threshold |
| Volcano plot inverted (down peaks on right) | Contrast direction reversed | `contrast = c('condition', 'treat', 'ctrl')` for positive log2FC = up in treat |

## References

- Stark R & Brown G 2011 Bioconductor (DiffBind)
- Lun ATL & Smyth GK 2016 Nucleic Acids Res 44:e45 (csaw)
- Love MI et al 2014 Genome Biol 15:550 (DESeq2)
- Robinson MD et al 2010 Bioinformatics 26:139 (edgeR; TMM)
- Helmuth J et al 2016 bioRxiv (NormR)
- Tu S et al 2021 Genome Res 31:131 (MAnorm2)
- Orlando DA et al 2014 Cell Rep 9:1163 (ChIP-Rx framework)
- Egan B et al 2016 PLoS One 11:e0166438 (ChIP-Rx protocol)
- Fursova NA et al 2019 Mol Cell 74:1020 (Rx-Input scaling)
- Jin H et al 2020 Bioinformatics 36:1270 (ChIPseqSpikeInFree)
- Blanco E et al 2021 NAR Genom Bioinform 3:lqab064 (SpikChIP)
- Patel L, Cao Y, Mendenhall EM, Benner C, Goren A 2024 Nat Biotechnol 42:1343 (review of spike-in normalization failure modes; PMC12266361)
- Bressan D et al 2024 NAR Genom Bioinform 6:lqae118 (SpikeFlow Snakemake pipeline)

## Related Skills

- chip-seq/peak-calling - Upstream peak calling for DiffBind input
- chip-seq/chipseq-qc - Replicate concordance required before differential
- chip-seq/spike-in-normalization - Detailed spike-in workflow and scaling factor calculation
- chip-seq/cut-and-run-tag - CUT&RUN/CUT&Tag uses E. coli spike-in (different from Drosophila ChIP-Rx)
- chip-seq/peak-annotation - Annotate differential peaks to genes/cCREs
- differential-expression/deseq2-basics - DESeq2 fundamentals
- differential-expression/edger-basics - edgeR quasi-likelihood framework
- atac-seq/differential-accessibility - Parallel ATAC differential workflow

## Usage Guide

# Differential Binding Analysis - Usage Guide

## Overview

Identifies differentially bound ChIP-seq regions between conditions. Distinguishes three distinct normalization problems (composition bias, trended/abundance-dependent bias, global shift) and matches each to the appropriate fix (RLE/TMM on reads-in-peaks, TMM on background bins, or spike-in scaling). Covers DiffBind (BAM + peaks), DESeq2/edgeR/PyDESeq2 (count matrix), csaw (sliding windows for global-shift-robust testing), NormR (control-aware), MAnorm2, and ChIPseqSpikeInFree.

## Prerequisites

```r
BiocManager::install(c('DiffBind', 'DESeq2', 'edgeR', 'csaw', 'apeglm', 'rtracklayer'))
BiocManager::install(c('normr', 'ChIPseqSpikeInFree'))   # optional
```

```bash
pip install pydeseq2 pandas numpy
```

## Quick Start

Tell the agent what to do:
- "Run DiffBind on my sample sheet with default normalization for a typical TF ChIP"
- "I'm comparing H3K27ac in HDAC-inhibitor-treated vs control cells; choose the right normalization"
- "Use csaw with sliding windows to detect global shifts in H3K27me3 after EZH2 inhibition"
- "I have spike-in Drosophila reads; apply ChIP-Rx scaling to my DESeq2 analysis"
- "Run differential binding with both reads-in-peaks and background-bin normalization and reconcile"
- "Suspect global shift but no spike-in; run ChIPseqSpikeInFree for post-hoc detection"
- "Run NormR for control-aware enrichment/depletion calling"

## Example Prompts

### Standard TF ChIP (local changes)
> "Run DiffBind on 6 samples (3 ctrl, 3 treat) for FOXA1 ChIP-seq. Use the default reads-in-peaks RLE normalization since the biology is localized TF rebinding."

### Global shift (HDACi / BETi / EZH2i)
> "Compare H3K27me3 in EZH2-inhibitor-treated vs DMSO. EZH2 inhibition reduces H3K27me3 genome-wide; use spike-in scaling. I have Drosophila S2 read counts per sample."

### Broad mark, no spike-in
> "Run csaw with 1 kb windows and background-bin TMM normalization for H3K27me3 differential. Merge significant windows within 5 kb."

### Suspected composition bias
> "DiffBind with default settings shows almost no differential peaks but the IGV signal is obviously different. Switch to `background=TRUE` and re-analyze."

### Post-hoc global shift detection
> "I didn't run spike-in. Use ChIPseqSpikeInFree to detect whether there's a global shift in my BET-inhibitor experiment."

### Sample sheet preparation
> "Create a DiffBind sample sheet from my 8 BAMs + narrowPeak files. Columns: SampleID, Condition, Replicate, bamReads, bamControl, Peaks, PeakCaller."

### Method reconciliation
> "DiffBind reports 50 differential peaks; csaw windows reports 300. Walk through reconciliation logic and decide which to trust."

## What the Agent Will Do

1. **Diagnose the normalization problem**: ask about expected global vs local changes (HDACi/BETi/EZH2i/dosage -> global; standard TF perturbation -> local); check MA plot loess curve after a default run
2. **Choose the appropriate tool/normalization** per the three-problem framework
3. **Build sample sheet** with SampleID, Condition, Replicate, bamReads, bamControl, Peaks, PeakCaller
4. **Run differential binding:**
   - DiffBind: `dba.count()` -> `dba.normalize()` -> `dba.analyze()`
   - DESeq2/edgeR: count matrix -> DESeqDataSet -> test
   - csaw: `windowCounts()` -> `normFactors()` -> `glmQLFTest()` -> merge
   - NormR: `diffR()` joint binomial mixture on bins
5. **Spike-in integration** if applicable; compute scaling factors from Drosophila/E. coli reads, pass via `sizeFactors()` or `DiffBind` spike-in fields
6. **Verify normalization**: `dba.normalize(obj, bRetrieve = TRUE)` for DiffBind; inspect MA loess curve
7. **Internal-control sanity check**: for spike-in, confirm blacklist regions show no signal change post-scaling
8. **Output**: differential peaks BED + log2FC + padj; volcano + MA + PCA + heatmap plots
9. **Document**: version, normalization choice, design formula, padj threshold, spike-in metadata in methods

## Tips

- **Always check the MA plot loess after default run.** A shifted curve indicates wrong normalization. This is a 60-second sanity check that saves hours of misinterpretation.
- **DiffBind 3.x defaults changed.** `summits=200` recenters narrow peaks (set FALSE for broad histones); blacklist filter on by default; `dba.normalize()` now required.
- **Pre-filtering for ChIP-seq is lighter than RNA-seq.** Peaks are already enriched regions; aggressive filtering removes condition-specific gains.
- **LFC shrinkage is for ranking, not significance.** apeglm-shrunk fold changes are better for volcano plots and downstream ranking but do NOT change padj.
- **edgeR QL-F controls type-I error better than DESeq2 Wald** for small replicate counts (n=2-3).
- **Spike-in is the gold standard for global shifts.** Apply via `sizeFactors()` (read-level), never multiply peak counts.
- **For broad marks, use full peak width (summits=FALSE) or csaw with 1-2 kb windows.** Narrow recentering loses domain-level biology.
- **PCA before differential**: samples should cluster by condition, not batch. If batch dominates, add batch term to design.
- **Document spike-in scaling factors in methods.** Patel et al 2024 found improper spike-in normalization is common; only about half of surveyed datasets had adequate matched input controls.

## Troubleshooting

### Almost no differential peaks despite obvious effect

Usually wrong normalization for the biology:
1. Check MA loess; if shifted off y=0, switch to `background=TRUE` (DiffBind) or spike-in
2. Global-shift drug? Spike-in required; no algorithmic fix works
3. Pre-filtering too aggressive -> `rowSums >= 1` only

### Differential peaks have wrong sign

1. Composition bias inverted the signal; switch normalization
2. Contrast direction reversed; verify `contrast = c('condition', 'treat', 'ctrl')` for positive log2FC = up in treat

### High noise / many marginal peaks

1. Loose ENCODE-pattern input peaks; pre-filter to IDR or naive-overlap passing
2. Low FRiP / failing ChIP; see chipseq-qc; failing QC samples produce noisy differential

### DiffBind very slow

`dba.count(obj, bParallel = TRUE)` for parallel counting. For large peak sets (>100k), consider csaw with windows instead.

### Spike-in scaling gives nonsense

1. Applied to peak counts instead of `sizeFactors()` -> fix application layer
2. Spike-in reads not deduplicated -> re-extract from BAM
3. Spike-in saturated (too many reads) -> verify titration linearity
4. Spike-in mismatch with target -> confirm spike-in genome (Drosophila for human/mouse; E. coli for CUT&RUN/Tag)
5. Internal control changes -> see chipseq-qc and re-validate

### `Error: condition has only one level`

Either factor has only one level or `Condition` column missing from sample sheet. Add at least two distinct conditions with ≥2 replicates each.

## Related Skills

- chip-seq/peak-calling - Generate consensus peaks for DiffBind input
- chip-seq/chipseq-qc - Replicate concordance required before differential testing
- chip-seq/spike-in-normalization - Spike-in workflow for global-shift experiments
- chip-seq/cut-and-run-tag - E. coli spike-in (CUT&RUN) vs Drosophila (ChIP-Rx)
- chip-seq/peak-annotation - Annotate differential peaks to genes/cCREs
- differential-expression/deseq2-basics - DESeq2 patterns
- differential-expression/edger-basics - edgeR QL-F framework
- atac-seq/differential-accessibility - Parallel ATAC workflow

## Bundled Files

- `chip-seq--differential-binding--examples--csaw_windows_diff.R` — copied from `examples/csaw_windows_diff.R`
- `chip-seq--differential-binding--examples--deseq2_from_counts.R` — copied from `examples/deseq2_from_counts.R`
- `chip-seq--differential-binding--examples--diffbind_analysis.R` — copied from `examples/diffbind_analysis.R`
- `chip-seq--differential-binding--examples--pydeseq2_from_counts.py` — copied from `examples/pydeseq2_from_counts.py`
