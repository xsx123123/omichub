# bio-atac-seq-atac-qc

> Bundled component reference for `atac-seq/atac-qc` (original source: `skills/bio_skills/atac-seq/atac-qc`).

ATAC-seq library quality control -- TSS enrichment, FRiP, fragment-size periodicity, library complexity (NRF/PBC1/PBC2), mitochondrial fraction, and ENCODE 4 thresholds. Use when assessing whether an ATAC-seq library passes ENCODE acceptance criteria, diagnosing transposition artefacts, comparing Omni-ATAC vs standard prep quality, or selecting which replicates to drop before peak calling.

## Instructions

## Version Compatibility

Reference examples tested with: deepTools 3.5+, Picard 3.1+, samtools 1.19+, bedtools 2.31+, ATACseqQC 1.26+, pysam 0.22+, pyBigWig 0.3+, numpy 1.26+, pandas 2.2+, MultiQC 1.21+.

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed package and adapt.

# ATAC-seq Quality Control

**"Does my ATAC library pass ENCODE quality criteria?"** -> Compute the seven canonical metrics (depth, alignment rate, mitochondrial fraction, library complexity, fragment-size periodicity, TSS enrichment, FRiP) and compare against ENCODE 4 thresholds, then diagnose failures.

- CLI: `picard CollectInsertSizeMetrics`, `samtools flagstat`, `samtools idxstats`
- CLI: `deeptools plotFingerprint`, `computeMatrix reference-point` + `plotProfile`
- R: `ATACseqQC::TSSEscore`, `ATACseqQC::fragSizeDist`, `ATACseqQC::PTscore`
- Python: custom NRF/PBC from coordinate hash; pyBigWig for TSS enrichment

## ENCODE 4 ATAC-seq Acceptance Thresholds

| Metric | Definition | Ideal | Acceptable | Reject | Source |
|--------|-----------|-------|------------|--------|--------|
| Nuclear reads (after dedup, no chrM) | Mapped, MAPQ >= 30, non-chrM, deduped | >= 50M | 25-50M | < 25M | ENCODE 4 ATAC-seq Standards |
| Alignment rate | Mapped / total reads | >= 95% | 80-95% | < 80% | ENCODE 4 |
| Mitochondrial fraction | chrM / total mapped | < 5% (Omni-ATAC), < 20% (standard) | 20-50% | > 50% | Corces 2017 (Omni-ATAC) |
| NRF (Non-Redundant Fraction) | Distinct positions / total reads | >= 0.9 | 0.7-0.9 | < 0.7 | Landt 2012 |
| PBC1 (PCR Bottlenecking Coefficient 1) | Positions w/ 1 read / Positions w/ >= 1 read | >= 0.9 | 0.7-0.9 | < 0.7 | Landt 2012 |
| PBC2 | Positions w/ 1 read / Positions w/ 2 reads | >= 3.0 | 1.0-3.0 | < 1.0 | Landt 2012 |
| TSS enrichment (hg38, GENCODE v29) | Avg signal at TSS / avg flanking | >= 7 | 5-7 | < 5 | ENCODE 4 |
| FRiP (Fraction Reads in Peaks) | Reads in MACS peaks / total | >= 0.3 | 0.2-0.3 | < 0.2 | ENCODE 4, Landt 2012 |
| Insert-size periodicity | NFR + mono-nuc + di-nuc peaks visible | Clear 3+ peaks | NFR + mono only | Flat / single peak | Buenrostro 2013 |

ENCODE thresholds are organism-specific. Mouse (mm10, GENCODE M21) TSS enrichment >= 5 is acceptable; non-model organisms have no published threshold (use cohort percentile rank instead). Methodology evolves; verify against the current ENCODE ATAC-seq Standards before reporting.

## TSS Enrichment: ENCODE Method vs ATACseqQC Method

The two most common implementations DO NOT produce identical scores.

| Method | Numerator | Denominator | Scaling |
|--------|-----------|-------------|---------|
| ENCODE pyTSSe / Kundaje gtsse | Mean signal in 100 bp window centered at TSS | Mean signal in 100 bp window at +/- 1900 to +/- 2000 bp (flanks) | Per-base normalization to flanks; reported as fold-enrichment |
| ATACseqQC TSSEscore | Sum signal in TSS +/- 100 bp | Sum signal at +/- 1000 bp flanking windows | Different window sizes; ratios are larger |
| deeptools plotProfile | Visual; numeric ratio not standardized | Reference-point matrix | No standard score; for visualization only |

**Trigger:** Comparing a TSS score across studies.

**Mechanism:** Different normalization windows shift the absolute number; ATACseqQC's TSSEscore is typically 2-3x ENCODE's because of the wider flank.

**Symptom:** Reported score 21 vs ENCODE-ideal 7 mismatch. Likely the calculator was ATACseqQC; the equivalent ENCODE score might be 8.

**Fix:** State which implementation was used. For ENCODE comparisons, use `pyTSSe` (Kundaje lab) or implement the ENCODE recipe directly.

```python
import numpy as np
import pyBigWig

def encode_tss_enrichment(bw_path, tss_bed, flank=2000):
    """ENCODE-style TSS enrichment: signal at TSS center / signal at flanks."""
    bw = pyBigWig.open(bw_path)
    profiles = []
    for line in open(tss_bed):
        chrom, start, end, *rest = line.strip().split('\t')
        tss = int(start)
        strand = rest[2] if len(rest) > 2 else '+'
        try:
            vals = bw.values(chrom, tss - flank, tss + flank)
            if vals is None or len(vals) != 2 * flank: continue
            if strand == '-': vals = vals[::-1]
            profiles.append(np.nan_to_num(vals))
        except RuntimeError:
            continue
    avg = np.nanmean(profiles, axis=0)
    flank_signal = np.mean(np.concatenate([avg[:100], avg[-100:]]))
    center_signal = np.mean(avg[flank - 50: flank + 50])
    return center_signal / flank_signal if flank_signal > 0 else 0.0
```

## Fragment-Size Periodicity Patterns

| Pattern | Visual signature | Interpretation | Action |
|---------|-----------------|----------------|--------|
| Strong tri-modal | NFR (~50bp) >> mono (~200bp) > di (~400bp) > tri (~600bp) peaks | Excellent transposition; well-positioned chromatin | Pass |
| Clear bi-modal | NFR + mono only, di and tri faint | Acceptable; common in Omni-ATAC | Pass |
| Single broad peak | Flat after NFR or no NFR | Over-transposition (too much Tn5) OR degraded chromatin | Reject; cannot distinguish nucleosomes |
| Inverted (mono >> NFR) | Mono peak dominant, NFR weak | Under-transposition OR chromatin condensation | Caution; peak counts will be low |
| Sharp 147 bp spike with no flanks | Tight peak at 147 bp | ChIP-seq input contamination (MNase-like) | Reject; not ATAC-grade |
| 10.4 bp helical periodicity overlay | Sub-peaks at 50, 60, 70, 80 bp on NFR | Excellent chromatin structure resolution; helical phasing visible | Pass; high-quality |

The 10.4 bp helical periodicity is a Buenrostro 2013 hallmark: it reflects the helical pitch of B-form DNA, with Tn5 preferring outward-facing minor grooves on nucleosomal DNA. Its presence is a positive QC indicator but not required.

## Per-Metric Failure Modes

### Mitochondrial fraction > 50%

**Trigger:** Standard ATAC-seq protocol on intact cells (no nuclear isolation), or insufficient detergent in lysis.

**Mechanism:** Mitochondrial DNA is naked (no histones), so Tn5 hyperactively cuts it. Without nuclear-isolation steps (Omni-ATAC pre-spin, OR digitonin lysis with mt removal), chrM dominates the library.

**Symptom:** `samtools idxstats sample.bam | awk '$1=="chrM"'` shows >50% of mapped reads on chrM.

**Fix:** Re-prep with Omni-ATAC (Corces 2017) or fast-ATAC. Re-running QC on chrM-stripped BAM hides the underlying problem; the wasted sequencing remains. If chrM fraction is 30-50%, the library may still be salvageable via chrM removal but yield is reduced.

### NRF / PBC1 / PBC2 below threshold

**Trigger:** Over-amplified library; low input cell count combined with high PCR cycles.

**Mechanism:** Each PCR cycle doubles starting fragments. With low complexity input (<5000 cells) and >12 cycles, distinct fragments saturate and reads pile up at identical positions. NRF measures unique fragments / total; PBC2 specifically detects multi-copy duplication.

**Symptom:** NRF < 0.7; PBC2 < 1.0; massive duplicate-removal loss in `samtools markdup`.

**Fix:** No fix post-hoc. Re-prep with more starting cells and fewer PCR cycles. Note: ATAC has *legitimate* duplicates at hyperaccessible sites (Tn5 cuts identically there), so NRF < 0.9 is not by itself fatal. The combined PBC1 < 0.7 + PBC2 < 1.0 + visual coverage pile-ups confirm true bottlenecking.

### TSS enrichment < 5

**Trigger:** Generic chromatin opening throughout the genome (over-transposition), OR genome build mismatch between TSS BED and BAM, OR strand-flip in TSS file.

**Mechanism:** TSS enrichment requires that signal at TSSs is >> signal in genomic flanks. Over-transposition flattens the signal landscape. Strand-flipped TSSs subtract real signal because TSSs on - strand are calculated from the wrong direction.

**Symptom:** TSS profile is flat or shows a slight dip at TSS center. Genome browser shows accessibility everywhere, not concentrated at promoters.

**Fix:** Verify genome build (mm10 vs mm39 differ in TSS positions); verify GTF strand column; confirm signal track was generated post-deduplication. If TSS profile is genuinely flat, library is over-transposed and not recoverable; lower transposition time / Tn5 concentration in next prep.

### FRiP < 0.2

**Trigger:** Signal too diffuse to call peaks (over-transposition), low TSS enrichment, OR peak set is too narrow / restrictive.

**Mechanism:** FRiP correlates with TSS enrichment because both measure how concentrated the signal is. A diffuse library will have low FRiP regardless of peak count.

**Symptom:** Peak count looks normal but FRiP < 0.15.

**Fix:** Check TSS enrichment first. If TSS is also low, the library is over-transposed. If TSS is OK but FRiP is low, the peak caller may be undercalling -- try `-p 0.01` (looser) and recalculate FRiP.

### Replicate correlation < 0.85

**Trigger:** Batch effect, technical artefact, or cell-state drift between replicate biological collections.

**Mechanism:** Pearson correlation on log-scaled binned counts (deepTools `multiBamSummary bins -bs 10000`) tracks coverage similarity. Below 0.85 indicates non-trivial divergence; ENCODE wants >= 0.9 for biological reps.

**Fix:** Check PCA; if reps cluster apart from condition, drop the outlier or rerun. If the divergence aligns with batch, add batch as a covariate downstream (DiffBind `~Batch + Condition`). Do not silently merge with bad correlation.

## Library Complexity (NRF, PBC1, PBC2)

**Goal:** Detect over-amplification or low-input bottlenecks.

**Approach:** Hash mapped read positions (or fragment 5' coordinates), tally how many positions have 1, 2, or more reads, and compute the three metrics.

```python
import pysam
from collections import Counter

def library_complexity(bam):
    pos_counts = Counter()
    total = 0
    with pysam.AlignmentFile(bam, 'rb') as bf:
        for r in bf.fetch():
            if r.is_unmapped or r.is_secondary or r.is_supplementary:
                continue
            if r.is_duplicate:                          # Mark, not skip; PBC counts pre-dedup
                pass
            total += 1
            key = (r.reference_name, r.reference_start, r.is_reverse)
            pos_counts[key] += 1
    distinct = len(pos_counts)
    histogram = Counter(pos_counts.values())            # {1: N1, 2: N2, ...}
    n1 = histogram.get(1, 0)
    n2 = histogram.get(2, 0)
    nrf = distinct / total if total else 0.0
    pbc1 = n1 / distinct if distinct else 0.0
    pbc2 = n1 / n2 if n2 else float('inf')
    return {'NRF': nrf, 'PBC1': pbc1, 'PBC2': pbc2, 'total': total, 'distinct': distinct}
```

`r.is_duplicate` is informational only here; ENCODE NRF/PBC are computed pre-deduplication on the raw mapped BAM.

## Cross-Replicate QC

```bash
# Spearman correlation (more robust than Pearson for ATAC)
multiBamSummary bins -bs 10000 -p 8 \
    --bamfiles rep1.bam rep2.bam rep3.bam \
    -o multi.npz

plotCorrelation -in multi.npz \
    --corMethod spearman --whatToPlot heatmap --skipZeros \
    -o spearman_heatmap.png

# Fingerprint (per-bin signal cumulative -- diagonal = no enrichment, sharp curve = good)
plotFingerprint -p 8 -b rep1.bam rep2.bam rep3.bam \
    --labels rep1 rep2 rep3 \
    --skipZeros --numberOfSamples 50000 \
    -o fingerprint.png \
    --outQualityMetrics fingerprint_metrics.txt
```

deepTools fingerprint quality metrics report a synthetic JS distance without a reference; the (non-synthetic) Jensen-Shannon distance column is only computed when a reference sample is supplied via `--JSDsample`. Larger values indicate stronger enrichment.

## Library Complexity Extrapolation (preseq)

**Goal:** Predict whether re-sequencing would rescue a low-NRF library, separating "library is bottlenecked" from "we just sequenced too shallow."

**Approach:** Fit preseq's rational-function (Pade) approximation of the Good-Toulmin power-series estimator on observed BAM read positions; extrapolate distinct-fragment yield as a function of additional sequencing depth.

```bash
# c_curve: observed complexity at current depth
preseq c_curve -B sample.bam -o sample.ccurve.tsv -s 1e6

# lc_extrap: predicted complexity at higher depth (extrapolation -e here 200M; preseq default -e is 1e10, step -s default 1M)
preseq lc_extrap -B sample.bam -o sample.lcextrap.tsv -e 200000000 -s 5000000
```

Interpretation: if `lc_extrap` shows distinct-fragment count flattening before 100M reads, the library is bottlenecked (re-sequencing won't help; re-prep needed). If it continues to climb, re-sequencing will recover more unique reads. Use alongside NRF/PBC1/PBC2 to decide library re-prep vs deeper sequencing.

## Sex-Chromosome QC

**Trigger:** Clinical-grade ATAC; biobank-scale studies; sample-mix-up detection.

**Mechanism:** chrY has minimal coverage in female samples; XIST locus (chrX) is highly accessible only in female cells (X-inactivation). Sample-swap or sex-misassignment detectable from these two loci.

```bash
# chrY read fraction
samtools idxstats sample.bam | awk '$1=="chrY"{print $3 / $2}'   # reads per bp

# XIST locus accessibility (chrX:73820651-73852753 in hg38)
samtools view -c sample.bam chrX:73820651-73852753
```

Female: chrY reads/bp ~0; XIST count high. Male: chrY reads/bp ~male coverage; XIST count low. Discrepancy with sample metadata flags swap.

## Cell-Cycle Effect on Accessibility

**Trigger:** Proliferating cell lines (K562, HEK293, HeLa); samples with high S/G2M signature.

**Mechanism:** Replication-associated chromatin opening adds 5-15% global accessibility shift in proliferating cells; without correction, condition-specific cell-cycle differences confound differential analysis.

**Detection:** Score cells/samples for S-phase signature (Macosko 2015 cell cycle gene set adapted for chromatin: regulated origin loci, replication-stress-response genes); for bulk ATAC, compute per-sample peak intersection with replication-origin atlas (Repli-seq peaks).

**Fix for differential:** Add S-phase score as covariate in DESeq2 design (`~Sphase + Condition`); for scATAC, regress on TF-IDF residuals analogous to Seurat CellCycleScoring.

## Spike-in QC (Drosophila or E. coli Chromatin)

**Trigger:** Studies where global accessibility shift is biological (HDAC inhibitor, DNMT inhibitor, differentiation).

**Mechanism:** Per-library normalization (RPM, CPM) erases global accessibility shifts because total reads are nominally constant. Exogenous chromatin spike-in (Drosophila S2 or E. coli Tn5-naive chromatin added pre-Tn5) provides an external scaling reference.

**Pipeline:** Align reads to a concatenated human + Drosophila reference; count spike-in reads per sample; normalize by spike-in (not by total reads). Reske 2020 Epigenetics Chromatin shows that normalization-method choice materially changes differential-accessibility results when a global accessibility shift is expected (ARID1A/PIK3CA endometrial-epithelium case study), motivating an external reference such as a chromatin spike-in.

**QC threshold:** spike-in fraction 0.5-5% of total reads is the workable range. Below 0.1% spike-in is unreliable; above 10% suggests too much spike-in (loss of cellular reads).

## Comprehensive QC Aggregation

**Goal:** Produce a per-sample report card with PASS/FAIL flags against ENCODE thresholds.

**Approach:** Compute each metric independently, compare to thresholds, write a tab-delimited report consumable by MultiQC.

```python
import json, subprocess, sys
from pathlib import Path

ENCODE_THRESHOLDS = {
    'nuclear_reads_M': (25, 50),                      # (min acceptable, ideal)
    'mt_fraction': (0.5, 0.05),                       # (max acceptable, ideal); inverted
    'NRF': (0.7, 0.9), 'PBC1': (0.7, 0.9), 'PBC2': (1.0, 3.0),
    'TSS_enrichment': (5.0, 7.0), 'FRiP': (0.2, 0.3),
}

def grade(value, thr_acceptable, thr_ideal, inverted=False):
    if inverted:
        return 'FAIL' if value > thr_acceptable else ('PASS' if value <= thr_ideal else 'WARN')
    return 'FAIL' if value < thr_acceptable else ('PASS' if value >= thr_ideal else 'WARN')

def report(metrics, out_tsv):
    rows = []
    for k, (acc, ideal) in ENCODE_THRESHOLDS.items():
        if k not in metrics: continue
        inverted = (k == 'mt_fraction')
        flag = grade(metrics[k], acc, ideal, inverted=inverted)
        rows.append((k, metrics[k], acc, ideal, flag))
    with open(out_tsv, 'w') as f:
        f.write('metric\tvalue\tacceptable\tideal\tflag\n')
        for r in rows: f.write('\t'.join(map(str, r)) + '\n')
```

## MultiQC Aggregation

```bash
# Run after generating per-sample QC outputs
multiqc \
    fastqc/ \
    picard/ \
    samtools_stats/ \
    macs2/ \
    deeptools/ \
    -o multiqc_report
```

MultiQC ingests Picard CollectInsertSizeMetrics, samtools flagstat, deepTools plotFingerprint output, and MACS peaks tables. It does NOT compute TSS enrichment or NRF; pipe a custom `_mqc.tsv` for those.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| TSS enrichment off by 3x from expected | Wrong implementation (ENCODE vs ATACseqQC) | State the formula; convert by recomputing |
| NRF = 1.0 exactly | BAM was already deduplicated -> all positions distinct | Compute NRF on raw mapped BAM (pre-dedup) |
| PBC2 = inf | No positions with 2 reads | Library is too sparse; PBC2 unreliable below ~5M reads |
| Mt fraction reported but BAM has no `chrM` | Mitochondrial chromosome named `MT`, `Mt`, or `chromosome:MT` | Match `samtools idxstats` chromosome name to the filter |
| Insert size distribution flat after Picard | Sample is single-end | Insert size only valid for paired-end; switch to deeptools fragmentSize |
| Replicates correlate poorly but PCA looks fine | High background dominates correlation | Use `--skipZeros`; or compute correlation on peak counts only |
| FRiP differs by 2x between identical pipeline runs | Peak set differs (q-value cutoff drift) | Pin caller version + cutoff; FRiP is peak-set-dependent |
| TSS enrichment lower than expected on Omni-ATAC | Used standard TSS BED on FFPE-prepped sample | FFPE TSSs are degraded; use peak-based metric instead |

## References

- Buenrostro JD et al 2013 Nat Methods 10:1213 (ATAC-seq protocol; fragment-size periodicity)
- Corces MR et al 2017 Nat Methods 14:959 (Omni-ATAC; mt fraction reduction protocol)
- Landt SG et al 2012 Genome Res 22:1813 (ENCODE/modENCODE QC framework, NRF/PBC definitions; the PBC1/PBC2 split is a later ENCODE-pipeline refinement)
- ENCODE 4 ATAC-seq Data Standards (encodeproject.org/atac-seq) -- canonical thresholds
- Ou J et al 2018 BMC Genomics 19:169 (ATACseqQC R package; TSSEscore implementation)
- Ramirez F et al 2016 Nucleic Acids Res 44:W160 (deepTools, plotFingerprint JSD)
- Daley T & Smith AD 2013 Nat Methods 10:325 (preseq library-complexity extrapolation model; the lc_extrap re-sequencing decision)

## Related Skills

- atac-seq/atac-peak-calling - FRiP requires peaks; QC drives accept/reject before calling
- atac-seq/nucleosome-positioning - Fragment-size analysis
- atac-seq/single-cell-atac - per-cell QC has different thresholds
- read-qc/quality-reports - upstream FastQC
- alignment-files/bam-statistics - samtools flagstat / idxstats
- alignment-files/duplicate-handling - dedup before NRF/PBC computation

## Usage Guide

# ATAC-seq Quality Control - Usage Guide

## Overview

Compute the seven canonical ATAC-seq QC metrics (depth, alignment rate, mitochondrial fraction, library complexity, fragment-size periodicity, TSS enrichment, FRiP) and grade each against ENCODE 4 acceptance thresholds. Diagnose specific failure modes (over-transposition, library bottlenecking, chromatin degradation, batch effects) and decide which replicates to drop before peak calling.

## Prerequisites

```bash
conda install -c bioconda samtools picard deeptools multiqc bedtools
pip install pysam pyBigWig numpy pandas matplotlib
```

```r
BiocManager::install(c('ATACseqQC', 'TxDb.Hsapiens.UCSC.hg38.knownGene', 'BSgenome.Hsapiens.UCSC.hg38'))
```

ENCODE blacklist (Amemiya 2019), GENCODE TSS BED (matched to genome build) required for TSS enrichment.

## Quick Start

Tell your AI agent what you want to do:
- "Score every ENCODE 4 ATAC QC metric and flag PASS/WARN/FAIL"
- "Compute TSS enrichment using the ENCODE pyTSSe formula, not ATACseqQC's"
- "Diagnose why fragment-size distribution is flat -- over-transposition vs degraded chromatin"
- "Calculate NRF, PBC1, and PBC2 from the raw mapped BAM (pre-dedup)"
- "Run plotFingerprint and compare fingerprint QC metrics across replicates (the plain JS distance column needs a --JSDsample reference)"

## Example Prompts

### ENCODE 4 Compliance Audit
> "Run a full ENCODE 4 ATAC-seq QC audit on three replicates: nuclear read depth, alignment rate, mt fraction, NRF/PBC1/PBC2, TSS enrichment (ENCODE method), FRiP using MACS peaks, and fragment-size periodicity. Flag any metric that fails ENCODE thresholds and recommend drop/keep per replicate."

### TSS Enrichment Reconciliation
> "My ATACseqQC TSSEscore is 21 but my collaborator says ENCODE wants >= 7. Compute the ENCODE pyTSSe-style score so we can compare apples to apples."

### Diagnosing Flat Fragment Distribution
> "Insert-size distribution shows one broad peak with no nucleosome periodicity. Diagnose the likely cause (over-transposition, degraded chromatin, MNase contamination) and tell me whether the library is salvageable."

### Library Complexity Investigation
> "NRF is 0.65 and PBC2 is 0.8. Confirm bottlenecking vs legitimate ATAC duplicates at hyperaccessible sites by checking pile-up coverage at top peaks."

### Replicate Reconciliation
> "Pearson correlation between rep2 and rep3 is 0.78 (others are 0.94). Run PCA on peak counts and check whether rep2 and rep3 cluster together by batch -- if so, plan to add batch as a covariate downstream."

### Cross-Study Comparison
> "Compare my TSS enrichment to a published study; we both used hg38 but different TSS sources. Recompute on the same GENCODE v29 protein-coding TSS file for parity."

## What the Agent Will Do

1. Run `samtools flagstat` and `samtools idxstats` for alignment summary and chrM count
2. Compute NRF / PBC1 / PBC2 on the pre-dedup mapped BAM (post-MAPQ-filter)
3. Generate fragment-size distribution with Picard CollectInsertSizeMetrics; classify periodicity pattern
4. Compute TSS enrichment (ENCODE pyTSSe convention by default; ATACseqQC if requested)
5. Calculate FRiP from MACS peaks
6. Run plotFingerprint (synthetic JS distance; the plain JS distance requires a --JSDsample reference); cross-replicate Spearman correlation via `multiBamSummary`
7. Aggregate everything via MultiQC
8. Grade each metric PASS/WARN/FAIL and write a per-sample report card

## ENCODE 4 Threshold Quick Reference

| Metric | Ideal | Acceptable | Reject |
|--------|-------|------------|--------|
| Nuclear reads (post-dedup, no chrM) | >= 50M | 25-50M | < 25M |
| Alignment rate | >= 95% | 80-95% | < 80% |
| Mt fraction (Omni-ATAC) | < 5% | < 20% | > 50% |
| NRF | >= 0.9 | 0.7-0.9 | < 0.7 |
| PBC1 | >= 0.9 | 0.7-0.9 | < 0.7 |
| PBC2 | >= 3.0 | 1.0-3.0 | < 1.0 |
| TSS enrichment (ENCODE) | >= 7 | 5-7 | < 5 |
| FRiP | >= 0.3 | 0.2-0.3 | < 0.2 |

## Fragment-Size Pattern Quick Reference

| Pattern | Diagnosis |
|---------|----------|
| NFR + mono + di + tri visible | Excellent |
| NFR + mono only, di faint | Acceptable (Omni-ATAC) |
| Single broad peak, no NFR | Over-transposition; reject |
| Mono >> NFR | Under-transposition; caution |
| Sharp 147 bp spike, no flanks | MNase-like; reject |
| 10.4 bp helical sub-peaks visible | High-quality structural resolution |

## Tips

- TSS enrichment formula MUST be specified: ENCODE pyTSSe and ATACseqQC TSSEscore differ by 2-3x because of window size choices. State which implementation was used.
- Compute NRF/PBC on the raw mapped BAM (after MAPQ filter, before dedup). Computing post-dedup gives NRF = 1.0 trivially.
- ENCODE mt-fraction thresholds assume Omni-ATAC. Standard ATAC-seq routinely shows 30-50% chrM and is still usable after chrM-stripping; mt > 50% is the practical reject line.
- NRF below 0.9 is not by itself fatal: ATAC has *legitimate* duplicates at hyperaccessible sites. Confirm bottlenecking with PBC1 < 0.7 + PBC2 < 1.0 + visual pile-ups.
- FRiP is peak-set-dependent. Pin the peak caller version and q-value cutoff before reporting FRiP across studies.
- Use Spearman correlation (not Pearson) for cross-replicate comparison; ATAC signal is heavy-tailed and Pearson is dominated by top peaks.
- The 10.4 bp helical periodicity in fragment-size distribution is a positive QC indicator, not a requirement. Its absence does not flag the library.
- For non-model organisms, ENCODE thresholds do not apply directly. Use cohort percentile rank (e.g., drop the bottom 10% of TSS enrichment within the cohort).
- multiBamSummary `--skipZeros` is mandatory for ATAC; otherwise empty regions dominate the correlation.

## Related Skills

- atac-seq/atac-peak-calling - QC informs which replicates to feed peak calling
- atac-seq/nucleosome-positioning - Detailed fragment-size analysis and V-plots
- atac-seq/single-cell-atac - per-cell QC with different thresholds
- read-qc/quality-reports - Upstream FASTQ QC
- alignment-files/bam-statistics - samtools flagstat / idxstats wrappers
- alignment-files/duplicate-handling - Pre-dedup before NRF/PBC computation

## Bundled Files

- `atac-seq--atac-qc--examples--atac_qc_metrics.R` — copied from `examples/atac_qc_metrics.R`
