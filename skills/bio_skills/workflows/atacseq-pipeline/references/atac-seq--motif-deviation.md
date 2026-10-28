# bio-atac-seq-motif-deviation

> Bundled component reference for `atac-seq/motif-deviation` (original source: `skills/bio_skills/atac-seq/motif-deviation`).

Analyze TF motif accessibility variability across samples or single cells using chromVAR. Use when identifying TF motifs whose accessibility correlates with conditions, computing per-sample motif z-scores after matched background correction, comparing to ArchR / Signac equivalents, or distinguishing motif-accessibility signal from per-site footprinting.

## Instructions

## Version Compatibility

Reference examples tested with: chromVAR 1.24+, motifmatchr 1.24+, JASPAR2024 0.99+, TFBSTools 1.40+, BSgenome.Hsapiens.UCSC.hg38 1.4+, SummarizedExperiment 1.32+, limma 3.58+, ggplot2 3.5+, Matrix 1.6+, ArchR 1.0.2+, Signac 1.13+.

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws unexpected errors, introspect the installed package and adapt rather than retrying.

# Motif Deviation (chromVAR)

**"Which TF motifs explain accessibility variation across my samples or cells?"** -> Compute per-sample (or per-cell) deviation z-scores: how many standard deviations above expectation each TF motif's accessibility falls, controlling for GC content and overall accessibility via matched background peak sets.

- R: `chromVAR::computeDeviations(counts, motifs)` -> per-sample z-scores
- R: `chromVAR::computeVariability(dev)` -> per-motif variance ranking
- Single-cell alternative: `Signac::RunChromVAR()` (wrapper with matched defaults) or `ArchR::addDeviationsMatrix()`

chromVAR answers a different question than footprinting: footprinting asks "is this specific motif site bound?", chromVAR asks "do peaks containing this motif have systematically more or less accessibility than expected?" The two are complementary.

## What chromVAR Computes

For each (motif, sample) pair:
- **Raw deviation** = Sum of accessibility at peaks containing the motif - expected from a matched-GC, matched-accessibility background.
- **Bias-corrected deviation** = Raw deviation / SD of background deviations.
- **Z-score** = (corrected deviation - mean across cells) / SD across cells. Reported as the principal output.

Z-scores are signed: positive = motif more accessible in this sample than population average; negative = less. Magnitudes 2-5 are typical for biologically interesting motifs; >5 indicates strong covariation with sample state.

## Algorithmic Taxonomy

| Tool | Input | Background | Output | Best for | Fails when |
|------|-------|------------|--------|----------|------------|
| chromVAR | Peak count matrix + motif annotations | Matched GC + accessibility (50 peaks per match by default) | Per-sample motif z-score | Bulk + single-cell (sparse-aware); cross-sample variability | < 1500 reads/sample (bulk) or < 500 cells/cluster (sc); too few peaks (< 5000) |
| Signac::RunChromVAR | Seurat single-cell ATAC object | Same as chromVAR (delegated) | Motif assay in Seurat object | Standard single-cell workflows in Seurat ecosystem | Same as chromVAR; needs Seurat object setup |
| ArchR::addDeviationsMatrix | ArrowFile + tile/peak matrix | ArchR's getBgdPeaks (matched on GC + log accessibility) | Per-cell deviation matrix in ArchR project | ArchR ecosystem; faster on large scATAC | ArchR-specific format; not portable to chromVAR objects |
| Signac::FindMarkers (with motifs as features) | Motif accessibility matrix from RunChromVAR | Per-cell-cluster | Differential motifs per cluster | Cluster-level differential | Differential test must be on z-scores; raw counts will mislead |
| TF activity inference (DecoupleR / SCENIC+) | Gene expression + motif activity | Multi-modal | TF activity score | Multi-omics integration | Requires paired RNA-seq; chromVAR alone is insufficient |

Methodology evolves; verify against current chromVAR (Schep 2017), ArchR (Granja 2021), and Signac (Stuart 2021) benchmarks before locking pipelines.

## chromVAR vs Footprinting -- Different Questions

| Question | Tool |
|----------|------|
| Does the bulk pattern of motif-containing peaks vary with condition? | chromVAR |
| Is THIS specific motif site bound by a TF? | TOBIAS / HINT-ATAC |
| Per-cell TF activity in scATAC | chromVAR (via Signac/ArchR) |
| Per-cell TF binding at specific sites | scprinter |
| TF activity correlated with gene expression | chromVAR + co-expression OR SCENIC+ |
| Which TF families distinguish my cell clusters? | chromVAR per-cluster z-scores |
| Differential bound vs unbound between conditions | TOBIAS BINDetect |

chromVAR is fundamentally a *summary statistic* over many motif sites. Footprinting is per-site classification. Use chromVAR when motif site count >> 100; use footprinting when specific sites matter.

## Per-Tool Failure Modes

### chromVAR -- Too few peaks or too few reads

**Trigger:** ATAC peakset < 5000 peaks; per-sample read depth < 1500 in peaks.

**Mechanism:** chromVAR's background sampling requires enough peaks to find matched GC + accessibility partners. Sparse sampling at low peak count creates correlated null distributions, inflating both positive and negative z-scores.

**Symptom:** Variability scores all > 5 (suspiciously high); top variable motifs are dominated by AT-rich or GC-rich sequences regardless of biology.

**Fix:** Verify peakset is at full ATAC scale (typically 50k-200k peaks). For sc ATAC, aggregate cells to clusters of >= 500 cells before running.

### chromVAR background peaks -- Default is good, custom requires care

**Trigger:** Calling `getBackgroundPeaks()` with non-default `niterations` or `bias`.

**Mechanism:** Default `niterations=50` yields 50 matched background peaks per foreground peak. Reducing `niterations` increases noise; increasing slows linearly without much accuracy gain.

**Symptom:** Custom backgrounds inflate variability when niterations < 30.

**Fix:** Stick to defaults unless benchmarking. If running on huge cell counts, test on subsample first.

### chromVAR on broadly accessible cell types -- Z-scores compressed

**Trigger:** Multiple cell types in dataset have very different overall accessibility magnitudes.

**Mechanism:** chromVAR's correction normalizes for total accessibility; cell types with high background accessibility have compressed z-scores even if their motif-specific signal is strong.

**Symptom:** PCA on z-scores does not separate cell types as cleanly as raw counts.

**Fix:** Run chromVAR per-cell-type-cluster (separate runs) when global accessibility differs by > 5x. Alternatively use ArchR's per-cluster background.

### chromVAR on bulk samples without enough variation -- All z-scores near zero

**Trigger:** All bulk samples are technical replicates or very similar.

**Mechanism:** Z-scores normalize across the sample population; if there is no across-sample variability, all z-scores collapse to zero.

**Symptom:** Variability ranking is unstable across runs; top motifs change.

**Fix:** chromVAR is designed for variability; if the dataset has only one biological condition replicated, use footprinting or differential accessibility instead. chromVAR needs 6+ samples with biological variation to be informative.

### Signac::RunChromVAR -- Motif matching mismatch

**Trigger:** Motif assay added before peak set finalized; peak coordinates change.

**Mechanism:** RunChromVAR matches motifs to peaks at the time it's called; if peaks change downstream (e.g., after merge), the motif annotations become stale.

**Symptom:** Some peaks have NA motif annotations; deviation matrix has missing entries.

**Fix:** Run `AddMotifs()` -> `RunChromVAR()` AFTER finalizing peakset. Re-run if peaks change.

### ArchR::addDeviationsMatrix -- TileMatrix vs PeakMatrix

**Trigger:** Calling on tile matrix when peak matrix is more appropriate.

**Mechanism:** ArchR can compute deviations on either tiles (regular bins) or peaks. Peaks are biologically meaningful; tiles add noise from intergenic background.

**Fix:** Use `matrixName='PeakMatrix'` after addReproduciblePeakSet. Tile-based deviations are mainly for embedding, not biology.

## Decision Tree by Setting

| Setting | Workflow |
|---------|---------|
| Bulk, 6+ samples, condition contrast | chromVAR + limma differential on z-scores; rank by FDR |
| Bulk, 3-5 samples | chromVAR; report variability ranking; differential underpowered |
| scATAC, Signac ecosystem | Signac AddMotifs + RunChromVAR; FindMarkers on motif assay |
| scATAC, ArchR ecosystem | ArchR addPeakMatrix + addDeviationsMatrix + getMarkerFeatures |
| Multimodal scATAC + scRNA | chromVAR + paired DE; consider SCENIC+ for TF -> target inference |
| Plant / non-model organism | chromVAR with custom motif PFM (from CIS-BP); custom BSgenome |
| Time-course bulk (5+ time points) | chromVAR z-scores -> spline regression on time; identify motifs with non-monotone trajectories |

## chromVAR Workflow (Bulk)

**Goal:** Compute per-sample TF-motif accessibility z-scores corrected for GC bias and total signal.

**Approach:** Build a SummarizedExperiment from peak counts, add GC bias, filter sparse samples and peaks, match JASPAR motifs to peaks, sample matched background peaks, then compute deviations and per-motif variability.

```r
library(chromVAR); library(motifmatchr); library(BSgenome.Hsapiens.UCSC.hg38)
library(JASPAR2024); library(TFBSTools); library(SummarizedExperiment)

peaks <- rtracklayer::import('consensus_peaks.bed')           # GRanges
counts <- as.matrix(read.delim('peak_counts.tsv', row.names=1))    # rows = peaks, cols = samples
se <- SummarizedExperiment(assays=list(counts=counts), rowRanges=peaks)
se <- addGCBias(se, genome=BSgenome.Hsapiens.UCSC.hg38)

# Filter: depth >= 1500 reads/sample, FRiP >= 0.15; drop peaks with < 10 total fragments
se <- filterSamples(se, min_depth=1500, min_in_peaks=0.15, shiny=FALSE)
se <- filterPeaks(se, non_overlapping=TRUE, min_fragments_per_peak=10)

# Motifs: JASPAR vertebrate CORE (default for human/mouse)
# JASPAR2024 + TFBSTools incompatibility (TFBSTools issue #39): getMatrixSet does not dispatch on the
# JASPAR2024 object directly. Open the SQLite handle and pass that to getMatrixSet instead.
library(RSQLite)
jaspar2024 <- JASPAR2024::JASPAR2024()
sq <- dbConnect(SQLite(), db(jaspar2024))
pfm <- getMatrixSet(sq, opts=list(collection='CORE', tax_group='vertebrates'))
# JASPAR2020 (older) accepts the package object directly: getMatrixSet(JASPAR2020, opts=...)
motif_ix <- matchMotifs(pfm, se, genome=BSgenome.Hsapiens.UCSC.hg38, p.cutoff=5e-05)

# Background peaks: matched GC + accessibility (default 50 iterations is fine)
bg <- getBackgroundPeaks(object=se, niterations=50)

# Compute deviations
dev <- computeDeviations(object=se, annotations=motif_ix, background_peaks=bg)
zscores <- deviationScores(dev)         # motif x sample matrix of z-scores (deviations() returns raw bias-corrected deviations)
variability <- computeVariability(dev) # per-motif variability ranking
```

## Differential Motif Activity (limma on z-scores)

**Goal:** Identify TF motifs whose chromVAR z-scores differ significantly between conditions.

**Approach:** Build a contrast design matrix, fit limma's linear model on the motif-x-sample z-score matrix with empirical Bayes moderation, and pull motifs at adjusted p < 0.05.

```r
library(limma)
groups <- factor(colData(se)$condition, levels=c('control', 'treated'))
design <- model.matrix(~groups)
fit <- lmFit(zscores, design); fit <- eBayes(fit)
diff_motifs <- topTable(fit, coef=2, number=Inf, p.value=0.05)   # adj.P.Val column
```

Use `adj.P.Val` (limma's BH FDR), not `FDR` (which limma does not return). `logFC` is the difference in z-scores between groups; magnitudes 0.5-2 typical.

## chromVAR for Single-Cell ATAC (Signac)

**Goal:** Compute per-cell TF-motif z-scores in a Seurat scATAC workflow and call cluster-marker motifs.

**Approach:** Open the JASPAR2024 SQLite handle, attach motifs to the Seurat object via AddMotifs, run RunChromVAR to build the chromvar assay, then call FindAllMarkers with mean.fxn=rowMeans for z-score-appropriate differential.

```r
library(Signac); library(Seurat); library(JASPAR2024); library(TFBSTools)
library(BSgenome.Hsapiens.UCSC.hg38); library(RSQLite)

# Assume `seurat_obj` has an ATAC assay with consensus peaks
# JASPAR2024 + TFBSTools workaround (see TFBSTools issue #39):
jaspar2024 <- JASPAR2024::JASPAR2024()
sq <- dbConnect(SQLite(), db(jaspar2024))
pfm <- getMatrixSet(sq, opts=list(collection='CORE', tax_group='vertebrates'))
seurat_obj <- AddMotifs(seurat_obj, genome=BSgenome.Hsapiens.UCSC.hg38, pfm=pfm)
seurat_obj <- RunChromVAR(seurat_obj,
                          genome=BSgenome.Hsapiens.UCSC.hg38,
                          new.assay.name='chromvar')
DefaultAssay(seurat_obj) <- 'chromvar'

# Per-cluster differential motifs.
# `mean.fxn` is the standard FindAllMarkers/FindMarkers control for the per-feature summary.
# `fc.name` controls the output column name and is accepted by Seurat 4.x/5.x; if it errors,
# fall back to renaming the output column post-hoc.
markers <- FindAllMarkers(seurat_obj, only.pos=TRUE, mean.fxn=rowMeans, fc.name='avg_diff')
```

`mean.fxn=rowMeans` is required for z-score-style data; the default fold-change function (designed for log-counts) makes no sense on chromVAR z-scores.

## chromVAR for Single-Cell ATAC (ArchR)

**Goal:** Compute per-cell TF-motif deviations and per-cluster marker motifs within the ArchR ecosystem.

**Approach:** Build the reproducible peakset, attach motif annotations from CIS-BP, sample matched background peaks, run addDeviationsMatrix to score motif z-scores, and call getMarkerFeatures on the MotifMatrix per cluster.

```r
library(ArchR)
proj <- addReproduciblePeakSet(proj, groupBy='Clusters', pathToMacs2='/path/macs2')
proj <- addPeakMatrix(proj)
proj <- addMotifAnnotations(proj, motifSet='cisbp', name='Motif')
proj <- addBgdPeaks(proj)
proj <- addDeviationsMatrix(proj, peakAnnotation='Motif')

# Per-cluster deviation summary
markersMotifs <- getMarkerFeatures(proj, useMatrix='MotifMatrix',
                                   groupBy='Clusters', useSeqnames='z')
```

ArchR uses `cisbp` by default (CIS-BP database, ~5000 motifs); switch to `JASPAR2020` for fewer, more curated motifs.

## Reconciling chromVAR vs ArchR vs Signac

| Pattern | Likely cause | Action |
|---------|--------------|--------|
| Top variable motifs disagree | Different motif databases (JASPAR vs CIS-BP) | Re-run with matched motif set |
| Z-scores correlate but magnitudes differ | Different background sampling | Inspect per-tool background; defaults are similar but not identical |
| Signac chromvar assay has NA values | Motifs added after peakset finalized | Re-run AddMotifs + RunChromVAR after peaks are stable |
| ArchR per-cluster signature differs from Signac | Different clustering; different cell membership | Standardize clustering before comparison |

**Operational rule:** chromVAR z-scores are tool-specific. For cross-study comparison, recompute on the same peakset with the same motif database; do not use stored z-scores from heterogeneous sources directly.

## Variability Score Interpretation

| Variability | Z-score range typical | Interpretation |
|-------------|----------------------|----------------|
| < 1 | -1 to +1 | Motif activity ~constant; not biologically variable |
| 1-2 | -2 to +2 | Modest variation; condition-driven possible |
| 2-5 | -3 to +5 | Strong cross-sample / cross-cluster variability; biologically interesting |
| > 5 | -5 to +10 | Major driver of cell-state differences; flagship hits |

Variability is the across-sample variance of z-scores; it ranks motifs without requiring condition labels. For unsupervised TF discovery (e.g., trajectory analysis) variability is the primary metric.

## Background Peak Matching Mathematics

**Trigger:** Tuning chromVAR's `getBackgroundPeaks` parameters; benchmarking against published results.

**Mechanism:** chromVAR matches each foreground peak to background peaks by GC content + total accessibility, using a bin size `bs` (default 50). For each foreground peak, the algorithm samples `niterations` (default 50) replacement peaks from the matching bins. Variance across these matched samples becomes the null reference.

**Threshold tuning:**
- **bs=50** (default): the GC/accessibility bin granularity; works for typical peaksets. For very small peaksets (< 2,000 peaks), lower `bs` to avoid empty bins.
- **niterations=50** (default): 50 matched background peaks per foreground peak. Reducing below 30 inflates noise; increasing above 100 yields diminishing returns.

For non-canonical genomes (mouse mm10 with different GC distribution), consider rebuilding bins manually with `quantile()` to ensure equal-sized bins.

## chromVAR vs scBasset for Single-Cell

| Tool | Approach | Best for | Limitation |
|------|---------|----------|------------|
| chromVAR | Matched-background z-score per motif | Standard sc workflow; integrated in Signac/ArchR | Linear; no sequence context beyond motif PWM |
| scBasset (Yuan & Kelley 2022) | Sequence CNN with per-cell projection | Higher cluster-discrimination accuracy than chromVAR; predicts cell states from sequence | Newer; ecosystem smaller; needs >= 100 cells per cluster for stable projection |
| Enformer-derived TF activity | Long-context Transformer | Cross-cell-type TF activity prediction; distal regulation | Pre-trained models cell-type-specific |
| DecoupleR ULM/MLM (Badia-i-Mompel 2022) | Multi-method consensus TF activity scoring | Multi-omics integration; aggregation across motif databases | Requires careful cell-x-motif input matrix |

For high-stakes per-cell TF activity, run chromVAR + scBasset and report the intersection. See atac-seq/deep-learning-atac for scBasset details.

## DecoupleR Multi-Method TF Activity

```python
import decoupler as dc   # 1.x API shown (pip install 'decoupler<2'); decoupler 2.x renamed these to dc.mt.ulm / dc.mt.mlm / dc.mt.consensus
# adata: AnnData with motif_x_cell deviation matrix as input
acts_ulm = dc.run_ulm(mat=adata.obsm['chromvar'], net=collectri_net,
                      source='source', target='target')
acts_mlm = dc.run_mlm(mat=adata.obsm['chromvar'], net=collectri_net,
                      source='source', target='target')
acts_consensus = dc.run_consensus(mat=adata.obsm['chromvar'], net=collectri_net)
```

DecoupleR aggregates multiple TF-activity inference methods (ULM, MLM, viper, GSVA, etc.). The consensus output is more robust than any single method to motif database biases.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| `Error in addGCBias`: missing `seqlengths` | GRanges object lacks chrom sizes | Use `seqlengths(peaks) <- seqlengths(genome)` first |
| All z-scores near zero | Too few samples or too little variation | chromVAR requires biological variation; use footprinting or differential instead |
| `getBackgroundPeaks` slow | Default niterations and large peakset | Default is fine; do not reduce iterations below 30 |
| Differential motifs all significant | FDR not applied; or compared identical samples | Apply BH correction; verify groups are correct |
| Signac chromvar assay all zero | RunChromVAR called before peakset | Re-run after AddMotifs and peakset stability |
| FindAllMarkers reports `avg_log2FC` for chromvar | Default fc method incorrect for z-scores | Use `mean.fxn=rowMeans` and `fc.name='avg_diff'` |
| z-score interpretation flipped | Sign of contrast reversed | Verify factor level order; first level is reference |
| ArchR `cisbp` vs `JASPAR2020` results differ | Different motif databases | Choose one and report the choice |

## References

- Schep AN et al 2017 Nat Methods 14:975 (chromVAR)
- Granja JM et al 2021 Nat Genet 53:403 (ArchR)
- Stuart T et al 2021 Nat Methods 18:1333 (Signac)
- Aibar S et al 2017 Nat Methods 14:1083 (SCENIC; downstream TF target inference)
- Bravo Gonzalez-Blas C et al 2023 Nat Methods 20:1355 (SCENIC+)
- Castro-Mondragon JA et al 2022 NAR 50:D165 (JASPAR 2022)
- Rauluseviciute I et al 2024 NAR 52:D174 (JASPAR 2024)
- Weirauch MT et al 2014 Cell 158:1431 (CIS-BP)
- Vorontsov IE et al 2024 NAR 52:D154 (HOCOMOCO v12)

## Related Skills

- atac-seq/footprinting - Per-site TF binding (different question)
- atac-seq/differential-accessibility - Peak-level DA (alternative approach)
- atac-seq/single-cell-atac - sc workflow integration with Signac/ArchR
- atac-seq/co-accessibility - Cis-regulatory connections
- atac-seq/deep-learning-atac - scBasset / Enformer alternative
- gene-regulatory-networks/scenic-regulons - Downstream TF -> target inference
- chip-seq/motif-analysis - Alternative motif-enrichment approaches
- single-cell/clustering - Inputs for per-cluster motif activity

## Usage Guide

# Motif Deviation (chromVAR) - Usage Guide

## Overview

Compute per-sample (or per-cell) TF motif accessibility z-scores using chromVAR. Identifies which motifs covary with sample/cell state, controlling for GC content and overall accessibility through matched background peak sets. Complements footprinting (which scores individual binding sites) with genome-wide motif-class summary statistics.

## Prerequisites

```r
BiocManager::install(c('chromVAR', 'motifmatchr', 'JASPAR2024', 'TFBSTools',
                       'BSgenome.Hsapiens.UCSC.hg38', 'SummarizedExperiment',
                       'limma', 'Signac', 'Seurat'))

# ArchR alternative (if using ArchR ecosystem)
remotes::install_github('GreenleafLab/ArchR', ref='master', repos=BiocManager::repositories())
```

Inputs:
- Peak count matrix (rows = peaks, cols = samples) OR Seurat/ArchR object
- Genomic ranges of peaks (BED or GRanges)
- Motif PFM database (JASPAR 2024 default; HOCOMOCO or CIS-BP for special cases)

## Quick Start

Tell your AI agent what you want to do:
- "Run chromVAR on a 12-sample bulk ATAC peak count matrix and report top variable motifs"
- "Run chromVAR per-cell on Signac scATAC object via RunChromVAR"
- "Compare motif z-scores between treatment groups using limma on the deviation matrix"
- "Use ArchR addDeviationsMatrix on PeakMatrix and rank cluster-marker motifs"
- "Verify chromVAR has enough peaks (>5000) and reads (>1500/sample) for stable inference"

## Example Prompts

### Bulk Analysis
> "Run chromVAR on this peak count matrix with JASPAR 2024 vertebrate CORE motifs. Add GC bias correction, filter samples below 1500 reads-in-peaks and FRiP < 0.15, then report top 20 most variable motifs and their z-score matrix."

### Differential Motif Activity
> "Run limma on the chromVAR z-score matrix to identify motifs differing between control and treated. Report adj.P.Val < 0.05 and abs(logFC) > 0.5; do not use raw counts."

### Single-Cell Signac
> "Add motifs to my Seurat object after the peakset is finalized, run RunChromVAR, then call FindAllMarkers on the chromvar assay with `mean.fxn=rowMeans` and `fc.name='avg_diff'` to find cluster-marker motifs."

### Single-Cell ArchR
> "In my ArchR project, add reproducible peakset, addPeakMatrix, addMotifAnnotations with `motifSet='cisbp'`, addBgdPeaks, addDeviationsMatrix. Then getMarkerFeatures on MotifMatrix grouped by Clusters."

### Validation
> "My chromVAR variability scores are all >5; verify peak count is at full ATAC scale (50k+) and per-sample reads-in-peaks > 1500. If too sparse, aggregate cells before running."

### Time-Course
> "Fit a spline regression on chromVAR z-scores across the time course; identify motifs with non-monotonic trajectories indicative of waves of TF activity."

## What the Agent Will Do

1. Verify peakset (>5000 peaks) and per-sample depth (>1500 reads-in-peaks for bulk)
2. Build SummarizedExperiment from counts + peak ranges
3. Add GC bias annotation (chromVAR requires genomic sequence)
4. Filter samples and peaks per chromVAR thresholds
5. Match motifs (JASPAR 2024 default; CIS-BP for non-model)
6. Sample matched background peaks (50 iterations; default is fine)
7. Compute deviation matrix (motif x sample)
8. Compute variability (per-motif variance across samples)
9. Optionally: differential testing via limma; per-cluster markers via FindMarkers / getMarkerFeatures
10. Generate visualization: variability plot, heatmap of top motifs, PCA

## Tool Decision Quick Reference

| Setting | Tool |
|---------|------|
| Bulk, 6+ samples | chromVAR + limma |
| Bulk, 3-5 samples | chromVAR; variability ranking only |
| scATAC, Seurat | Signac::RunChromVAR -> FindAllMarkers |
| scATAC, ArchR | addDeviationsMatrix -> getMarkerFeatures |
| Multiomics scATAC + scRNA | chromVAR + paired DE; or SCENIC+ |
| Plant / non-model | chromVAR with custom CIS-BP motifs and BSgenome |

## Variability Interpretation Quick Reference

| Variability | Interpretation |
|-------------|----------------|
| < 1 | Motif activity ~constant |
| 1-2 | Modest variation |
| 2-5 | Strong variation; biologically interesting |
| > 5 | Major driver; flagship hit |

## chromVAR vs Footprinting Decision

| Question | Use |
|----------|-----|
| Which TFs distinguish my conditions/clusters? | chromVAR |
| Is THIS specific motif site bound? | Footprinting (TOBIAS/HINT) |
| Per-cell TF activity for trajectory analysis | chromVAR (Signac/ArchR) |
| Motif activity correlated with paired RNA | chromVAR + co-expression OR SCENIC+ |

## Tips

- chromVAR requires biological variation across samples to be informative. With only one condition replicated, use footprinting or differential accessibility instead.
- Minimum thresholds: 5000+ peaks, 1500+ reads-in-peaks per sample (bulk), 500+ cells per cluster (single-cell). Below these, z-scores are unreliable.
- Default `niterations=50` for `getBackgroundPeaks` is well-calibrated; reducing it adds noise, increasing it doesn't help. Don't tune unless benchmarking.
- chromVAR z-scores are NOT comparable across studies that use different peak sets or different motif databases. Recompute for cross-study comparison.
- Use BH-adjusted p-values from limma (`adj.P.Val`) for differential motif testing on z-scores; raw t-tests are mis-calibrated.
- For single-cell, run `RunChromVAR()` AFTER finalizing the peakset; otherwise motif annotations become stale.
- ArchR's `cisbp` motif set has ~5000 motifs (broader); JASPAR has ~1900 (more curated). Choose based on whether breadth or precision is needed.
- chromVAR is fundamentally a *summary statistic*. For per-site analysis, use footprinting; for differential peak counts, use DiffBind.
- The variability score does not require condition labels and is a good unsupervised discovery tool. Z-scores require labels for differential.
- When global accessibility differs >5x between cell types in the dataset, run chromVAR per-cluster separately rather than jointly.

## Related Skills

- atac-seq/footprinting - Per-site TF binding analysis
- atac-seq/differential-accessibility - Peak-level differential
- atac-seq/single-cell-atac - sc workflow integration
- atac-seq/co-accessibility - Cis-regulatory follow-up
- gene-regulatory-networks/scenic-regulons - Downstream TF -> target networks
- chip-seq/motif-analysis - Alternative motif enrichment
- single-cell/clustering - Cluster definition for per-cluster analysis

## Bundled Files

- `atac-seq--motif-deviation--examples--chromvar_analysis.R` — copied from `examples/chromvar_analysis.R`
