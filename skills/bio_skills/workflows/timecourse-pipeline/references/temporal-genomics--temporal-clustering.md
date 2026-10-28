# bio-temporal-genomics-temporal-clustering

> Bundled component reference for `temporal-genomics/temporal-clustering` (original source: `skills/bio_skills/temporal-genomics/temporal-clustering`).

Clusters temporally variable genes by expression-profile SHAPE (not significance) using Mfuzz fuzzy c-means, TCseq, DEGreport degPatterns, and tslearn DTW/soft-DTW. Use when grouping pre-selected time-course genes into shared trajectory programs (co-expression modules), choosing between soft vs hard clustering, picking k, selecting a distance metric (Euclidean/correlation/DTW), or interpreting clusters with per-cluster enrichment. Requires temporally variable genes selected FIRST (differential-expression/timeseries-de or a variance filter); clustering is descriptive and downstream of selection, never a test of which genes are dynamic.

## Instructions

## Version Compatibility

Reference examples tested with: Mfuzz 2.64+, TCseq 1.14+, DEGreport 1.30+ (R/Bioconductor); tslearn 0.8+, scikit-learn 1.4+ (Python).

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show tslearn scikit-learn` then `help(module.function)` to check signatures
- R: `packageVersion('Mfuzz')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Temporal Gene Clustering

**"Group my time-course genes by expression pattern shape"** -> Partition PRE-SELECTED temporally variable genes into co-expression modules by trajectory shape (fuzzy c-means, hierarchical, or DTW), producing candidate temporal programs.
- R: `Mfuzz::mfuzz()` (fuzzy/soft), `TCseq::timeclust()`, `DEGreport::degPatterns()`
- Python: `tslearn.clustering.TimeSeriesKMeans` (Euclidean / DTW / soft-DTW)

## Governing Principle - read before clustering anything

Clustering answers only "which genes share a temporal SHAPE." It is DESCRIPTIVE and UNSUPERVISED: it has no null model, no p-value, and no notion of a "true" cluster count, so it ALWAYS returns clusters from whatever it is handed. It is strictly DOWNSTREAM of gene selection.

- It does NOT answer "which genes are rhythmic" (that is temporal-genomics/circadian-rhythms) and does NOT answer "is this gene significantly changing" (that is differential-expression/timeseries-de: LRT, spline-DE, maSigPro). Clustering adds description, not inference.
- The input MUST already be the temporally variable genes - the output of timeseries-DE or, at minimum, a variance filter. Never the full expression matrix.
- **Feeding in flat/all genes is the #1 error.** Per-gene z-scoring (mandatory, below) rescales a flat gene's pure noise to unit variance, so it lands in a "cluster" of noise that mimics a real program. Z-scoring erases the one signal (near-zero variance) that flagged the gene as flat, which is exactly why prefiltering is a gate, not optional hygiene.
- Clusters are HYPOTHESES. A centroid is a candidate program; membership is not evidence a gene is regulated - that evidence came (or did not) from the upstream DE step.

If a user asks "cluster my RNA-seq time course," the first question is always: have these genes already been selected for temporal change, and how? If the answer is "no, it is all 20,000 genes," stop and prefilter.

## Core Workflow

1. Confirm the input is pre-selected temporally variable genes (DE hits or top-variance); if not, prefilter
2. Standardize each gene's profile (z-score across timepoints) - mandatory
3. Choose a distance metric (Euclidean-on-zscore / correlation / DTW), then an algorithm and k
4. Assign genes to clusters (soft membership or hard labels); filter by membership if fuzzy
5. Validate by stability (bootstrap/consensus), then interpret centroids and run per-cluster enrichment with the correct background

## Soft vs Hard, and Why Standardization Is Mandatory

**Soft (fuzzy) clustering is preferred for expression.** Genes participate in multiple regulatory programs, so forcing one gene into one cluster (hard k-means) is biologically false at boundaries and brittle: a gene between two centroids flips clusters under trivial noise. Futschik & Carlisle (2005) established fuzzy c-means as noise-ROBUST for expression time courses - low-membership (ambiguous, likely-noise) genes are down-weighted in centroid estimation, so centroids track the high-confidence core of each program, and ambiguity is exposed as a continuous membership score to threshold rather than hidden inside a hard label.

**Z-score per gene is mandatory** (Mfuzz `standardise()`, TCseq `standardize=TRUE`, tslearn `TimeSeriesScalerMeanVariance()`). Without it, MAGNITUDE dominates SHAPE: a high-abundance housekeeping gene sits far (Euclidean) from a low-abundance gene of identical shape, while two high-abundance genes co-cluster on abundance alone. Clustering-by-shape requires removing each gene's mean and scaling to unit variance across timepoints.

## Mfuzz (R/Bioconductor)

**Goal:** Group temporally variable genes into soft co-expression clusters by trajectory shape.

**Approach:** Build an ExpressionSet, gate out flat genes (`filter.std`), z-score (`standardise`), estimate then VALIDATE the fuzzifier, run fuzzy c-means, and filter genes by membership. Mfuzz wraps `e1071::cmeans` (it does not implement its own optimizer); distance is Euclidean on z-scored profiles.

### Setup and Preprocessing

```r
library(Mfuzz)
library(Biobase)

# Rows = genes (already selected as temporally variable), columns = timepoints (mean across replicates)
expr_mat <- as.matrix(read.csv('temporal_expression.csv', row.names = 1))
eset <- ExpressionSet(assayData = expr_mat)

# filter.std: flat-gene GATE (keeps the governing principle true). min.std=0.5 is a starting
# point; inspect the SD distribution and set it above the flat-gene noise floor for your data.
eset <- filter.std(eset, min.std = 0.5)

# Per-gene mean 0, sd 1 across timepoints (British spelling; no 'standardize' alias)
eset <- standardise(eset)
```

### Fuzzifier Estimation - inspect, do not trust blindly

**Goal:** Pick a fuzzifier `m` that keeps clusters informative for THIS number of timepoints.

**Approach:** `mestimate()` implements Schwaemmle & Jensen (2010): it returns the smallest `m` that stops fuzzy c-means from finding tight clusters in RANDOMIZED data. The estimate is dominated by D (number of timepoints) via a D^-2 term, so it can go degenerate at the extremes - inspect the returned `m` AND the membership distribution rather than trusting either the estimate or the historical `m=2` default.

```r
# With FEW timepoints (small D), mestimate pushes m HIGH -> over-fuzzy: memberships flatten
# toward 1/c and an acore(0.5) filter can discard nearly everything.
# With MANY timepoints (large D), m falls toward ~1.05-1.2 -> near-hard, soft advantage evaporates.
m <- mestimate(eset)
cat(sprintf('Estimated fuzzifier m: %.2f\n', m))

cl <- mfuzz(eset, c = 8, m = m)  # c=8: starting point for 6-12 timepoints; refine below

# VALIDATE m: what fraction of genes clears the alpha-core cutoff? If very few do, m is too high.
max_mem <- apply(cl$membership, 1, max)
cat(sprintf('Genes with max membership >= 0.5: %.0f%%\n', 100 * mean(max_mem >= 0.5)))
# Sanity check the estimate's own criterion: cluster a permuted copy; it should NOT form tight clusters.
```

### Membership Filtering and Cluster Selection

```r
# acore returns, per cluster, genes with MAX membership >= min.acore ("alpha cores").
# 0.5 is a convention; it discards a data-dependent fraction (larger m -> more discarded).
# Relaxing to 0.3 is legitimate for exploratory work but admits more noise. Always report the retained fraction.
core_genes <- acore(eset, cl, min.acore = 0.5)

# Minimum centroid distance vs k: as k grows the closest centroid pair collapses; a knee hints at
# over-splitting. This is a WEAK, monotone-ish signal, not an oracle -- triangulate with stability (below).
min_dist <- sapply(4:20, function(k) {
    d <- as.matrix(dist(mfuzz(eset, c = k, m = m)$centers))
    diag(d) <- Inf
    min(d)
})
plot(4:20, min_dist, type = 'b', xlab = 'k', ylab = 'Min centroid distance')
```

### Visualization

```r
mfuzz.plot2(eset, cl, mfrow = c(2, 4), time.labels = colnames(expr_mat), centre = TRUE, x11 = FALSE)
overlap.plot(cl, over = overlap(cl), thres = 0.05)  # centroid-overlap view; merges hint at over-clustering
```

## TCseq (R/Bioconductor)

TCseq was built for time-course SEQUENCING (RNA-seq/ATAC-seq); upstream DE/peak steps live in the same package, and `timeclust` clusters the summarized (per-gene, per-timepoint) matrix.

```r
library(TCseq)

# algo='cm': fuzzy c-means (soft, Mfuzz-like). Also 'km' (hard k-means), 'pam', 'hc' (hierarchical).
# standardize=TRUE does the mandatory per-gene z-score.
tc <- timeclust(expr_mat, algo = 'cm', k = 6, standardize = TRUE)
timeclustplot(tc, value = 'z-score', cols = 3)

tc_km <- timeclust(expr_mat, algo = 'km', k = 6, standardize = TRUE)  # hard alternative
```

## DEGreport degPatterns (R)

**Goal:** Hierarchical clustering with automatic k and design-aware grouping.

**Approach:** `degPatterns` takes replicate-level data plus metadata, collapses samples within each (time, col) group to a MEAN internally, then clusters on correlation distance and cuts the tree. Convenient, but "auto k" is really "cut + merge under `minc`," a heuristic - not an optimum.

```r
library(DEGreport)

# time, col: COLUMN NAMES in metadata (col defaults to NULL). minc=15: minimum cluster size;
# clusters smaller than minc are DROPPED -- this both blocks singletons AND silently discards genes,
# so it can yield fewer clusters than the tree suggested. Set deliberately.
patterns <- degPatterns(expr_mat, metadata = sample_info, time = 'timepoint', col = 'condition', minc = 15)

cluster_df <- patterns$df                     # gene -> cluster assignments
degPlotCluster(patterns$normalized, time = 'timepoint', color = 'condition')  # note: 'color', not 'col'
```

## tslearn (Python) - Euclidean / DTW / soft-DTW

**Goal:** Cluster time-series profiles, optionally warping the time axis for phase-shifted genes.

**Approach:** Z-score, then `TimeSeriesKMeans`. The DISTANCE METRIC matters more than the algorithm - default to Euclidean-on-zscore (which, after standardization, is monotone in Pearson correlation and captures "same shape, different amplitude"). Escalate to DTW ONLY for real, expected phase shifts, and ALWAYS constrain it.

```python
import numpy as np
from tslearn.clustering import TimeSeriesKMeans, silhouette_score
from tslearn.preprocessing import TimeSeriesScalerMeanVariance

# expr_mat: (n_genes, n_timepoints) of PRE-SELECTED temporally variable genes
expr_scaled = TimeSeriesScalerMeanVariance().fit_transform(expr_mat[:, :, np.newaxis])

# Default, safe choice: Euclidean on z-scored profiles (phase-SENSITIVE, cheap, no fabricated structure)
model = TimeSeriesKMeans(n_clusters=8, metric='euclidean', max_iter=50, random_state=42)
labels = model.fit_predict(expr_scaled)
```

### DTW - powerful for phase shifts, but constrain the band or it invents structure

DTW (Sakoe & Chiba 1978) warps the time axis so a profile peaking one timepoint later can still match - the ONLY reason to reach for it (signaling cascades, developmental heterochrony, unequal sampling). Its default failure mode is the SINGULARITY: unconstrained DTW maps one point of series A onto a long run of points of series B, manufacturing apparent co-regulation from noise. tslearn's default `global_constraint=None` is exactly this singularity-prone configuration.

```python
# The Sakoe-Chiba BAND caps how far in time a point may be matched -- kills most singularities AND
# cuts cost. This constraint is mandatory, not optional, for DTW clustering.
# sakoe_chiba_radius: warping-window half-width in timepoints; small (1-2) for tight sampling.
model = TimeSeriesKMeans(
    n_clusters=8, metric='dtw',
    metric_params={'global_constraint': 'sakoe_chiba', 'sakoe_chiba_radius': 2},
    max_iter=50, random_state=42)
labels = model.fit_predict(expr_scaled)

# Soft-DTW: replaces DTW's hard min with a soft-min -> DIFFERENTIABLE loss, enabling proper
# soft-DTW barycenters (cluster centers). It is NOT "faster" -- still quadratic; use it for smooth,
# well-defined averaging, not speed. gamma via metric_params (NOT the deprecated gamma_sdtw kwarg).
soft = TimeSeriesKMeans(n_clusters=8, metric='softdtw', metric_params={'gamma': 0.5},
                        max_iter=50, random_state=42)
```

**When DTW is worth it:** only when phase shift is real and expected, the band is set, AND DTW has been checked against fabricating structure. On data with NO phase shifts, DTW should not beat Euclidean - if it "finds more clusters" there, that is invented structure, not signal.

### Selecting k - score under the SAME geometry that formed the clusters

```python
# Scoring DTW clusters with a EUCLIDEAN silhouette is geometrically inconsistent: clusters were
# formed under DTW geometry but ranked under Euclidean, which can pick a DIFFERENT (wrong) k.
# tslearn.clustering.silhouette_score takes metric='dtw'/'softdtw' and precomputes the matching
# distances internally -- score under the SAME geometry that formed the clusters.
dtw_params = {'global_constraint': 'sakoe_chiba', 'sakoe_chiba_radius': 2}
scores = {}
for k in range(3, 11):
    km = TimeSeriesKMeans(n_clusters=k, metric='dtw', metric_params=dtw_params, max_iter=30, random_state=42)
    labels_k = km.fit_predict(expr_scaled)
    scores[k] = silhouette_score(expr_scaled, labels_k, metric='dtw', metric_params=dtw_params)
best_k = max(scores, key=scores.get)
```

Under a pure-Euclidean pipeline, `sklearn.metrics.silhouette_score(expr_scaled.squeeze(), labels)` is consistent and fast. It is only the DTW/Euclidean MISMATCH that mis-ranks k.

## Choosing k - the honest story

No index is authoritative; triangulate and let biology and stability decide.

| Signal | What it says | Caveat |
|---|---|---|
| Min centroid distance / Dmin | knee where centroids start collapsing = over-splitting | weak, monotone-ish |
| Silhouette | within- vs nearest-other-cluster separation | must match the clustering metric (DTW vs Euclidean) |
| Within-cluster dispersion / elbow / gap | dispersion drop-off | elbow subjective; gap assumes a null reference, expensive |
| Biology heuristic | does +1 cluster split a coherent program or resolve two real shapes? | the honest arbiter |
| **Stability (bootstrap/consensus)** | do the same genes co-cluster under resampling? | **the real validation, not a lone index** |

Over-clustering FRAGMENTS one real program across centroids (the same GO terms then reappear in three clusters); under-clustering MERGES distinct programs into an averaged centroid matching no gene. Report a stable partition, not a single silhouette peak.

## Distance Metric - it dominates the algorithm choice

| Metric | Captures | Phase shifts | Cost | Use when |
|---|---|---|---|---|
| Euclidean on z-score | shape + amplitude (monotone in Pearson after z-score) | NO | cheap | default for aligned timepoints |
| Correlation (DEGreport) | shape, amplitude-invariant | NO | cheap | shape-only focus |
| DTW (constrained) | shape with time warping | YES | O(n·T^2)/pair, worse for clustering | genuine, expected phase shifts only |

## The Circularity / Double-Dipping Trap

Selecting genes by a temporal criterion, clustering them, then TESTING those clusters for the same temporal signal is circular and inflates everything. If genes were selected for temporal variability, a follow-up test asking "are these clusters temporally structured / rhythmic?" is guaranteed to say yes - the signal was baked in at selection (Kriegeskorte-style non-independence). Interpreting per-cluster centroid p-values after DE selection is the same error: the genes are already significant by construction. Selection -> clustering is fine as a DESCRIPTIVE pipeline; what is not permissible is a test on the same data whose null was already violated by selection. Test clusters only against INDEPENDENT annotations (GO, TF targets, a held-out condition), never the temporal criterion used to select.

## Per-Cluster Enrichment - the background-set trap

Run GO/GSEA per cluster to name programs, but the enrichment BACKGROUND (universe) must be the INPUT gene set that was clustered (the temporally variable genes), NOT the whole genome. Genome-as-background makes every cluster light up for the generic biology of "being a dynamic/expressed gene" (translation, stress, cell cycle) - that signal comes from the SELECTION step, not the cluster, and re-tests what was already done (mirrors the circularity trap). Testing cluster-vs-(rest-of-input) isolates what makes THIS shape distinct.

## Replicate Handling

The examples cluster on replicate-AVERAGED profiles (standard and simple), but averaging DISCARDS uncertainty the DE step had: two genes with identical means but very different within-timepoint variance are treated as equally reliable. `degPatterns` makes the collapse explicit (mean within each time/col group) but still computes similarity on group means. The rigorous-but-rare alternative is a variance-aware/weighted distance; at minimum, state that averaging is a known limitation.

## Method Comparison

| Method | Clustering | Distance | Best for |
|--------|-----------|----------|----------|
| Mfuzz | Soft (fuzzy c-means) | Euclidean on z-score | standard soft temporal profiling |
| TCseq | Soft (`cm`) or hard (`km`/`pam`/`hc`) | Euclidean on z-score | RNA-seq/ATAC time courses |
| DEGreport | Hierarchical, auto-k | Correlation | design-aware, quick auto-k |
| tslearn | Hard k-means | Euclidean / DTW / soft-DTW | phase-shifted profiles (constrained DTW) |

## Common Errors

| Trap | Why it is wrong | Fix |
|---|---|---|
| Clustering ALL genes (incl. flat) | no null -> always returns clusters; z-score amplifies flat-gene noise into fake programs | prefilter to timeseries-DE hits or `filter.std`/top-variance FIRST |
| Skipping z-score | magnitude dominates shape; abundance clusters, not dynamics | `standardise()` / `standardize=TRUE` / `TimeSeriesScalerMeanVariance()` |
| Hardcoding `m=2` or trusting `mestimate()` blindly | m=2 over-fuzzy for many timepoints; mestimate degenerates at extreme D | inspect returned m + membership fraction; check it does not cluster randomized data |
| Treating k as having a "true" value | indices disagree; clustering has no true count | triangulate indices + biology + bootstrap stability |
| Unconstrained DTW | singularities invent structure from noise | set `global_constraint='sakoe_chiba'`; use DTW only for real phase shifts |
| "soft-DTW is just faster DTW" | still quadratic; its value is differentiability/barycenters | use soft-DTW for smooth averaging, not speed |
| Euclidean silhouette to pick k for DTW clusters | scores a different geometry than formed the clusters -> mis-ranks k | `tslearn.clustering.silhouette_score(..., metric='dtw')`, or cluster Euclidean throughout |
| Testing clusters for the temporal signal selected on | circular / double-dipping; p-values inflated | test only INDEPENDENT annotations |
| GO enrichment vs whole-genome background | re-detects "being dynamic" from the selection step | background = the clustered input gene set |
| Reporting centroids as if genes follow them exactly | centroid is an average; membership/spread varies | report membership (acore) fraction + within-cluster spread |

## References

- Futschik ME, Carlisle B (2005). Noise-robust soft clustering of gene expression time-course data. J Bioinform Comput Biol 3(4):965-988. (Original noise-robustness rationale for fuzzy c-means on expression time courses.)
- Kumar L, Futschik ME (2007). Mfuzz: a software package for soft clustering of microarray data. Bioinformation 2(1):5-7.
- Schwaemmle V, Jensen ON (2010). A simple and fast method to determine the parameters for fuzzy c-means cluster analysis. Bioinformatics 26(22):2841-2848. (Implemented by `mestimate()`; fuzzifier depends on the number of timepoints.)
- Cuturi M, Blondel M (2017). Soft-DTW: a Differentiable Loss Function for Time-Series. PMLR 70:894-903. (Differentiable soft-min smoothing of DTW; gamma controls smoothing.)
- Sakoe H, Chiba S (1978). Dynamic programming algorithm optimization for spoken word recognition. IEEE Trans Acoust Speech Signal Process 26(1):43-49. (Foundational DTW and the Sakoe-Chiba warping-window band.)
- Bezdek JC (1981). Pattern Recognition with Fuzzy Objective Function Algorithms. Plenum Press, New York. (Foundational fuzzy c-means and the fuzzifier m.)

## Related Skills

- circadian-rhythms - Rhythm detection by phase (answers "which genes are rhythmic", not shape clustering)
- trajectory-modeling - Continuous trajectory fitting before clustering
- differential-expression/timeseries-de - Upstream temporal DE that selects the genes to cluster
- pathway-analysis/go-enrichment - Per-cluster functional enrichment (use the input gene set as background)

## Usage Guide

# Temporal Gene Clustering - Usage Guide

## Overview

Groups PRE-SELECTED temporally variable genes by expression-profile SHAPE into candidate co-expression programs. Clustering is descriptive and unsupervised - it has no null and always returns clusters - so it is strictly downstream of gene selection (differential-expression/timeseries-de or a variance filter), NOT a test of which genes are dynamic. Supports soft (fuzzy) clustering with Mfuzz, hard/soft clustering with TCseq, automatic-k hierarchical clustering with DEGreport, and DTW/soft-DTW clustering with tslearn for phase-shifted patterns.

## Prerequisites

### R
```r
BiocManager::install(c('Mfuzz', 'TCseq', 'DEGreport'))
```

### Python
```bash
pip install tslearn scikit-learn numpy matplotlib
```

### Data Requirements
- Expression matrix (genes x timepoints), typically averaged across replicates
- Pre-filtered for temporally variable genes (e.g., via limma or DESeq2 LRT)
- At least 4 timepoints; 6-12 timepoints is ideal for meaningful clustering

## Quick Start

Tell the AI agent what to cluster:
- "Cluster my time-course genes by expression profile shape using Mfuzz"
- "Group my differentially expressed genes into temporal response patterns"
- "Find genes with similar trajectories using DTW clustering"
- "Run degPatterns on my RNA-seq time-course data"

## Example Prompts

### Soft Clustering
> "I have 2000 temporally variable genes across 8 timepoints. Cluster them with Mfuzz soft clustering and filter for core members."

> "Run fuzzy c-means clustering on my time-series expression data and show me the cluster centroids."

### Automatic Clustering
> "Use DEGreport degPatterns to automatically determine the number of temporal clusters in my RNA-seq data."

> "Cluster my time-course genes and automatically pick the best number of clusters."

### DTW-Based Clustering
> "Some of my genes have phase-shifted responses. Cluster them using DTW distance in Python."

> "Run time-series k-means with dynamic time warping on my expression profiles."

### Post-Clustering Analysis
> "After clustering, run GO enrichment on each temporal cluster to identify pathway themes."

> "Show me which transcription factors are enriched in each temporal expression cluster."

## What the Agent Will Do

1. Confirm the input is pre-selected temporally variable genes; if it is the full matrix, prefilter (DE hits or top-variance) before clustering
2. Standardize expression profiles (z-score per gene across timepoints)
3. Choose a distance metric (Euclidean-on-zscore / correlation / constrained DTW) appropriate to whether phase shifts are expected
4. Estimate and VALIDATE the fuzzifier (Mfuzz) and triangulate k across indices, biology, and bootstrap stability (not a single index)
5. Run clustering (Mfuzz, TCseq, DEGreport, or tslearn) and filter genes by membership
6. Interpret centroids as candidate programs; generate profile plots
7. Run per-cluster enrichment using the INPUT gene set as background, avoiding the double-dipping trap
8. Export cluster assignments for downstream analysis

## Tips

- Prefilter FIRST: cluster only temporally variable genes (timeseries-DE hits or a variance filter). Clustering all genes is the #1 error - z-scoring amplifies flat-gene noise into fake programs, and clustering has no null so it always returns clusters.
- Always standardize (z-score per gene) before clustering; raw values let high-expression genes dominate on magnitude instead of shape.
- Start with Mfuzz (soft) for most tasks; its continuous membership exposes ambiguous genes rather than hiding them in a hard label.
- Do not hardcode m=2 and do not trust mestimate() blindly: it implements Schwaemmle & Jensen (2010), is dominated by the number of timepoints, and can go degenerate at extreme D. Inspect the returned m and the fraction of genes clearing the acore cutoff.
- Membership threshold 0.5 for Mfuzz is a convention; relax to 0.3 for exploratory work (admits more noise). Always report the retained fraction.
- The distance metric matters more than the algorithm. Default to Euclidean-on-zscore or correlation. Use DTW only when phase shifts are biologically expected (e.g., signaling cascades), always with a Sakoe-Chiba band - unconstrained DTW invents structure. Soft-DTW is not faster (still quadratic); its value is a differentiable, well-defined average.
- Pick k by triangulation, not one index: min centroid distance, silhouette (scored under the clustering metric), biology, and above all bootstrap/consensus STABILITY.
- Do not test clusters for the temporal signal used to select them (double-dipping inflates p-values); test only against independent annotations.
- Run per-cluster GO/GSEA with the INPUT gene set as background, never the whole genome - genome-as-background rediscovers the selection.
- For large gene sets (>10,000), pre-filter to the top variable genes to keep clustering tractable (and correct).

## Related Skills

- temporal-genomics/circadian-rhythms - Rhythm-specific clustering by phase
- temporal-genomics/trajectory-modeling - Continuous trajectory fitting
- differential-expression/timeseries-de - Upstream temporal DE for gene selection
- pathway-analysis/go-enrichment - Per-cluster functional enrichment

## Bundled Files

- `temporal-genomics--temporal-clustering--examples--mfuzz_clustering.R` — copied from `examples/mfuzz_clustering.R`
- `temporal-genomics--temporal-clustering--examples--tslearn_clustering.py` — copied from `examples/tslearn_clustering.py`
