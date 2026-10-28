# bio-chipseq-peak-calling

> Bundled component reference for `chip-seq/peak-calling` (original source: `skills/bio_skills/chip-seq/peak-calling`).

Calls ChIP-seq peaks with MACS3, MACS2, HOMER, or SPP across narrow (TF) and broad (histone) modes. Handles input control matching, fragment-size modeling vs --nomodel, effective genome size, ENCODE-style IDR vs naive overlap, hyper-ChIPable artifacts, and aligner-specific shifts. Use when calling peaks from ChIP-seq alignments, choosing between narrow vs broad mode for a histone mark, deciding model vs nomodel for low-depth data, applying ENCODE pseudoreplicate IDR, or reconciling MACS vs HOMER vs SPP results.

## Instructions

## Version Compatibility

Reference examples tested with: MACS3 3.0.4+, MACS2 2.2.9+, HOMER 4.11+, SPP 1.16+, samtools 1.19+, bedtools 2.31+, IDR 2.0.4+.

Before running, verify versions: `<tool> --version` and `<tool> --help` to confirm flags. If a flag is missing, check the changelog — MACS2->MACS3 is API-compatible for `callpeak` but `predictd`, `bdgpeakcall`, and `hmmratac` differ.

# ChIP-seq Peak Calling

**"Identify protein-DNA binding sites from ChIP-seq alignments"** -> Detect statistically enriched genomic regions by comparing IP signal to input control (or genomic background), with peak shape (narrow/broad) determined by target biology (TF vs histone mark).

- CLI (ENCODE TF default): `macs2 callpeak -t chip.bam -c input.bam -f BAM -g hs -n sample --keep-dup all -p 1e-2`
- CLI (ENCODE histone default): same with `--broad --broad-cutoff 0.1` for H3K27me3, H3K9me3, H3K36me3
- CLI (alternative): `macs3 callpeak ...` (API-identical, active development), HOMER `findPeaks tags/ -style histone -i input_tags/`, SPP via phantompeakqualtools wrapper

ENCODE TF pipeline still uses **SPP for peak ranking + IDR**, with MACS2 producing the signal tracks. Histone pipeline uses **MACS2 + naive overlap** (IDR is too conservative for histone signal dynamic range). MACS3 is the actively maintained successor; MACS2 receives only bug fixes.

## Critical Pre-Call Validation

Before any peak calling, three things must be true or the output is unreliable:

1. **Antibody validated** — KO/KD orthogonal control, peptide-array specificity for histone modifications, or vendor-provided CRISPR-validated lot (Epicypher, CST). "ChIP-grade" marketing is not validation. See chipseq-qc.
2. **Fragment-size distribution is sane** — TF ChIP should show sub-nucleosomal (~50-100 bp) enrichment; histone ChIP should show clean mono- (~150) and di-nucleosomal (~300) peaks. Flat distribution = over-sonication; rescue is impossible. Check via `samtools view -f 0x2 sample.bam | awk '{print $9}' | sort | uniq -c`.
3. **Input control matches** — Sonicated input is biased toward open chromatin; MNase input toward nucleosomes. Input from a different library prep batch or fragmentation method introduces bias that subtraction cannot fix.

## Algorithmic Taxonomy

| Tool | Model | Treats fragments as | Strength | Fails when |
|------|-------|---------------------|----------|------------|
| MACS3/MACS2 callpeak | Dynamic local Poisson (max of genome-wide, 1kb, 5kb, 10kb lambda) + BH-FDR | Single-end shifts; PE fragments via BAMPE | Mature, fast, ENCODE-default, narrow + broad modes, integrated signal tracks | Confounds NFR with broad accessible domains; default narrow mode segments broad enrichment; assumes most genome NOT enriched (breaks for genome-wide marks) |
| SPP (Kharchenko 2008) | Strand cross-correlation peak detection + Poisson fold-enrichment | Single-end with cross-corr-derived shift | ENCODE TF caller; integrated NSC/RSC QC; robust for sharp TF peaks | Underperforms for broad marks; older R codebase; phantompeakqualtools wrapper has R-version compatibility issues |
| HOMER `-style factor` | Fixed-width peaks + three sequential filters (control / local / clonal) | Tag positions; auto-estimated width | Fast on tag directories; clonal filter `-C` removes PCR-artifact peaks | Less calibrated p-values; fixed width clips variable-width factor binding |
| HOMER `-style histone` | Variable-width region stitching (500 bp blocks, 1000 bp gap merging); L=0 (no local enrichment) | Tag positions | Captures variable-width histone enrichment; Omnipeak benchmark (Shpynov & Artyomov 2026): outperforms `-style factor` for histone marks including H3K4me3 | Less sensitive than MACS for very sharp TF binding |
| Genrich `-y` (ChIP mode) | q-value on log-transformed p-value, joint replicate model | Whole fragments (PE intervals) | Joint replicate analysis; chrM exclusion via `-e chrM`; auto blacklist via `-E` | Less peer-reviewed than MACS/SPP; thin literature; control handling less mature |
| MACS3 hmmratac | 3-state HMM on fragment-size signal | Fragment-size classes | Best for ATAC, not ChIP | Wrong tool for ChIP; ChIP fragment-size distribution doesn't drive useful HMM states |
| SEACR (Meers 2019) | Empirical threshold on signal block totals | Bedgraph signal blocks | Designed for sparse CUT&RUN/CUT&Tag data; "stringent" mode with IgG strongly preferred | Not for traditional ChIP-seq (assumes near-zero background); see cut-and-run-tag |
| LanceOtron (Hentges 2022) | CNN trained on ENCODE peaks | bigWig signal | Competitive for both narrow and broad without parameter tuning | Newer; less validated; web-only or pip install |

For CUT&RUN / CUT&Tag specifically, see chip-seq/cut-and-run-tag — protocol differences (lower depth, IgG-only control, E. coli spike-in carryover) drive different caller choice (MACS2 + SEACR consensus, not MACS3 alone).

## Decision: Narrow vs Broad

Driven by target biology, not preference. Calling broad mode does not make a sharp signal broad; it changes how MACS stitches adjacent enrichment.

| Target | Mode | Why |
|--------|------|-----|
| Transcription factors (CTCF, p53, GATA1, FOXA1) | Narrow (default) | Discrete motif binding produces sharp peaks |
| H3K4me3, H3K27ac at promoters/enhancers | Narrow | Localized at regulatory elements |
| H3K4me1 at enhancers | Narrow or broad-cutoff 0.1 | Variable; check published data for the cell type |
| H3K36me3, H3K79me2 (elongation) | Broad | Deposited across active gene bodies (5-50 kb domains) |
| H3K27me3, H3K9me3 (repressive) | Broad | Spread across 10-100+ kb domains |
| H4K20me3 (constitutive het) | Broad | Heterochromatin domains |
| Pol II (RNAPII) | Narrow at promoter + broad option for elongation profile | Two separate analyses if doing elongation biology |

For HOMER: use `-style histone` for ALL histone marks (Omnipeak benchmark, Shpynov & Artyomov 2026 NAR 54:gkaf1454); `-style factor` ONLY for transcription factors.

## Decision: Model vs --nomodel

MACS2/3 fragment-size modeling needs ≥100 paired plus/minus enrichment regions within `--mfold` (default `[5, 50]`). Silent failure produces wrong fragment size and warped peaks — always inspect `_model.r` output.

| Condition | Model? | Fallback |
|-----------|--------|----------|
| Whole-genome, ≥1M treatment reads, narrow TF | Yes | `--mfold 3 50` if fails |
| Paired-end with `-f BAMPE` | N/A | Fragment size from mate pairs |
| Single chromosome or targeted capture | No | `--nomodel --extsize <data-derived or mark default>` |
| Low read count (<500k) | No | Same |
| Broad histone mark | Either | Mark-type default if no estimate available |

When `--nomodel` is required, choose `--extsize` in priority order: (1) cross-correlation estimate from phantompeakqualtools (ENCODE standard, gives NSC/RSC simultaneously); (2) `macs3 predictd -i chip.bam -g hs` and read stderr; (3) mark-type fallback (147 for nucleosome-proximal marks, 200 for broader marks).

## Effective Genome Size — Often Wrong, Always Matters

`-g hs` (2.7e9) and `-g mm` (1.87e9) are decade-old approximations. Modern read-length-matched values (deepTools `effectiveGenomeSize` table):

| Genome | Read length | Effective size |
|--------|-------------|----------------|
| hg38 | 50 bp | 2.701e9 |
| hg38 | 75 bp | 2.748e9 |
| hg38 | 100 bp | 2.806e9 |
| hg38 | 150 bp | 2.862e9 |
| mm10 | 50 bp | 2.308e9 |
| mm10 | 100 bp | 2.467e9 |

Wrong size shifts every q-value but rarely peak ranks. For subset data (single chromosome, targeted), provide numeric `-g <bp>`; the shorthand inflates lambda_BG by 60× and produces false positives at low-signal regions.

## Hyper-ChIPable Regions Are a Persistent Artifact

Teytelman 2013 (PNAS) and Park 2013 (PLoS One) demonstrated that highly-transcribed genes (rRNA, tRNA, histone gene cluster, snoRNA hosts, mitochondrial-encoded genes, abundant housekeeping loci) appear "bound" in ChIP-seq with untagged GFP, no antibody, or non-existent targets. ENCODE blacklist v2 catches repeat-driven artifacts but NOT these hyper-ChIPable transcribed regions.

Always interpret peaks at rRNA loci, tRNA clusters, replication-dependent histone genes (HIST1/2 clusters), mitochondrial DNA, and the top-1% input-signal regions with skepticism. For rigorous claims: (1) require motif enrichment at the peak (artifact has no motif); (2) require KO/KD signal loss; (3) build a cell-type-specific blacklist from the top 1% of input signal and intersect-out.

## Pipeline Reference: ENCODE TF vs Histone

**TF pipeline (uses SPP for peak ranking):**

```bash
# Per-replicate (loose) — IDR tightens downstream
macs2 callpeak -t rep1.tagAlign.gz -c input.tagAlign.gz \
    -f BED -g hs -n rep1 \
    --nomodel --shift 0 --extsize {fraglen_from_xcor} \
    --keep-dup all -B --SPMR -p 1e-2

# Repeat for rep2, pooled, and pseudoreplicates (split each rep into halves)
# Score peaks by signalValue, sort, run IDR (see Replicate Handling below)
```

**Histone pipeline (uses MACS2 broad / narrow + naive overlap):**

```bash
# Broad marks: H3K27me3, H3K9me3, H3K36me3
macs2 callpeak -t rep1.tagAlign.gz -c input.tagAlign.gz \
    -f BED -g hs -n rep1 \
    --broad --broad-cutoff 0.1 \
    --nomodel --shift 0 --extsize {fraglen} \
    --keep-dup all -B --SPMR -p 1e-2

# Naive overlap: a peak passes if it appears in ≥2 of N replicates
# with ≥40% reciprocal overlap (ENCODE default, often misquoted as 50%)
bedtools intersect -a rep1.broadPeak -b rep2.broadPeak -f 0.40 -r -u > naive_overlap.bed
```

`--keep-dup all` is intentional in the ENCODE pattern: duplicates were already filtered upstream by MarkDuplicates + `samtools view -F 1804 -q 30`. `-p 1e-2` is permissive because IDR (TF) or overlap (histone) tightens downstream.

## Replicate Handling: IDR vs Naive Overlap

ENCODE rules (Landt 2012 *Genome Res*):

**TFs use IDR.** Run on signal-ranked peaks (sort by `-k8,8nr` p-value; `-k7,7nr` signal works for SPP but breaks for MACS pile-up if libraries differ).

```bash
sort -k8,8nr rep1.narrowPeak > rep1.sorted
sort -k8,8nr rep2.narrowPeak > rep2.sorted

idr --samples rep1.sorted rep2.sorted \
    --input-file-type narrowPeak --rank p.value \
    --idr-threshold 0.05 --output-file true_reps.idr --plot
```

**ENCODE Nself/Nt consistency rule** (often misremembered):
- Nt = IDR-passing peaks across true biological replicates (threshold 0.05)
- Nself (per rep) = IDR-passing peaks across pseudoreplicates of one library (threshold 0.10)
- Library passes if `max(N1self, N2self) / min(N1self, N2self) ≤ 2` AND `max(Nt, max(Nself)) / min(Nt, min(Nself)) ≤ 2`
- Both ratios > 2: library rejected

**Histones use naive overlap.** IDR's high-vs-low-rank assumption breaks for histone dynamic range. Naive overlap: pool peaks, require each to appear in ≥2 replicates with ≥40% reciprocal overlap.

## ENCODE 3 vs ENCODE 4 Differences

| Feature | ENCODE 3 | ENCODE 4 |
|---------|----------|----------|
| TF peak ranker | SPP | SPP (unchanged) |
| Histone caller | MACS2 | MACS2 (MACS3 not yet adopted) |
| Aligner | bwa-mem | bwa-mem (chromap evaluated; not yet swapped) |
| Blacklist | v1 (ENCODE DAC, unpublished resource) | v2 (Amemiya 2019) |
| TF significance | `-p 1e-2` + IDR @ 0.05 | Same |
| Histone significance | `-p 1e-2` + naive overlap | Same |
| Effective genome size | `hs`/`mm` shorthand | deepTools read-length-tabulated |
| Pseudoreplicate IDR threshold | 0.10 self-consistency | 0.10 self-consistency |

ENCODE 4 outputs are NOT numerically comparable to ENCODE 3 on the same BAM (blacklist change + genome size update shift peak counts ~3-10%).

## Per-Tool Failure Modes

### MACS2/3 -- Silent fragment-size model failure

**Trigger:** Sparse signal, low replicate depth, or saturated samples; `_model.r` plot never inspected.

**Mechanism:** Model needs ≥100 paired plus/minus enriched regions in `--mfold` range. Below threshold, MACS picks an arbitrary fragment size (often 50 or 1000 bp), producing miscentered or oversized peaks. Stderr shows a warning that gets ignored.

**Symptom:** Peak summits shifted relative to known motif positions by hundreds of bp; visual inspection in IGV shows peaks displaced from pile-up centers.

**Fix:** Inspect `<sample>_model.r` — if peaks look reasonable, accept; if degenerate, widen with `--mfold 3 50` or switch to `--nomodel --extsize <data-derived>`. For consistency across samples in a study, always use `--nomodel --extsize {fraglen}` with cross-correlation-derived fraglen (ENCODE pattern).

### MACS2/3 -- Confounded narrow vs broad on intermediate marks

**Trigger:** Marks of intermediate breadth (H3K4me1, H3K9ac) called with default narrow mode.

**Mechanism:** Default narrow mode fragments wide enrichment into multiple sub-peaks; `--broad` over-stitches.

**Symptom:** Peak count 3-5× higher than published for same cell type; mean peak width < 200 bp at known enhancer regions.

**Fix:** For H3K4me1, try `--broad --broad-cutoff 0.1` and compare; for H3K9ac, narrow mode typically OK. Always cross-reference published peak counts for the cell type and antibody lot.

### MACS2/3 -- `--call-summits` double-counts

**Trigger:** Narrow mode + `--call-summits` flag.

**Mechanism:** MACS adds sub-peak summits at multi-mode pile-ups; broad-shouldered peaks get split into 2-3 entries.

**Symptom:** Peak count inflated; same genomic region appears as 2-3 adjacent peaks in narrowPeak output.

**Fix:** Drop `--call-summits` unless deliberately analyzing multi-mode binding (rare); merge `bedtools merge -d 200` if needed post-hoc.

### HOMER -- Wrong style for histones

**Trigger:** `-style factor` used for histone marks.

**Mechanism:** Factor mode uses fixed-width peaks with local enrichment filter `-L 4` that eliminates broad signal.

**Symptom:** Far fewer peaks than expected for H3K4me3/H3K27ac/H3K27me3; missed enrichment at known regions.

**Fix:** Use `-style histone` for ALL histone marks (Omnipeak benchmark, Shpynov & Artyomov 2026); reserve `-style factor` for TFs only.

### SPP / phantompeakqualtools -- R version incompatibility

**Trigger:** Running phantompeakqualtools wrapper script with R ≥ 4.0.

**Mechanism:** spp R package has unmaintained dependencies; some functions silently fail or return NaN for NSC/RSC.

**Fix:** Use conda env pinned to R 3.6 + spp 1.16; or use kundajelab/phantompeakqualtools fork (current); or substitute deepTools plotFingerprint for QC and MACS-derived fragment length.

### chromap aligner -- Pre-applied shift double-counts

**Trigger:** Using chromap (fast aligner) output as MACS input with `--shift -75 --extsize 150`.

**Mechanism:** chromap pre-applies a Tn5/cut-site shift before fragment output (designed for ATAC); ChIP cut-site reasoning doesn't apply but the shift still happens silently.

**Symptom:** Peaks shifted ~5-10 bp from bwa-mem output at the same locus.

**Fix:** When using chromap, drop downstream shift OR use chromap's `--no-correction`. For ChIP, bwa-mem or bowtie2 are safer defaults until ENCODE switches.

## Reconciliation: When Callers Disagree

| Pattern | Likely cause | Action |
|---------|--------------|--------|
| MACS finds peak; HOMER misses | HOMER local-enrichment filter (`-L 4`) removed it at low-signal regions; or `-style factor` clipped a histone peak | Re-run HOMER with `-style histone -L 0` for histones; if persists, trust MACS |
| HOMER finds peak; MACS misses | Clonal filter `-C 2` retained PCR artifact peaks; or HOMER's auto-width captured something MACS narrow mode segmented | Check if MACS broad mode rescues; check IGV for visual confirmation |
| SPP and MACS narrow peaks differ by 10-50 bp summit | Different fragment-size estimates (SPP uses cross-corr; MACS models from data) | Use same fragment size for both: ENCODE pattern `--nomodel --extsize {xcor_fraglen}` |
| MACS narrow + MACS broad on same data: 10× peak count difference | Expected — broad mode stitches subpeaks within 1 kb gap | Use narrow for differential analysis (consistent units); broad for domain annotation |
| Per-rep MACS calls peak; pooled MACS does not | One replicate dominates; pooling smooths local lambda | Trust pooled + IDR over per-replicate counts |
| Replicate count differs >2× | One replicate failed | Check FRiP, NSC, library complexity per replicate; do NOT average — drop the failing replicate or repeat |

**Operational rule for publication-grade:** TFs require IDR ≤ 0.05 on true reps AND Nt/Nself ratios ≤ 2. Histones require naive overlap ≥2 reps with ≥40% reciprocal overlap. Both require FRiP, NSC, RSC, and library complexity thresholds met. See chipseq-qc.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| 0 peaks called | Wrong genome size on subset data; wrong `-f` for input format; swapped treatment/control | Provide numeric `-g`; match `-f` to file type (BAM/BAMPE/BED); verify `-t` is enriched sample |
| Peak count >> 500k | Did not deduplicate; chrM not removed; `-q` too loose; hyper-ChIPable artifacts dominate | Filter `samtools view -F 1804 -q 30`; remove chrM; tighten to `-q 0.01`; blacklist top-1% input regions |
| Peaks shifted from motif by ~75 bp | `--shift` not set for `-f BAM`; or fragment-size model wrong | Add `--shift 0 --extsize {fraglen}`; or check `_model.r` |
| `--shift/--extsize ignored` warning | Used `-f BAMPE` with these flags | Switch to `-f BAM` for ENCODE pattern, or accept that BAMPE uses true fragment spans |
| IDR returns 0 reproducible peaks | Sorted by wrong column; ranks effectively random | `sort -k8,8nr` (p-value descending) on each peakset |
| Naive overlap returns few peaks | Set `-f 0.5 -r` (50% reciprocal) — too strict | Use `-f 0.40 -r` (ENCODE default) |
| FRiP < 1% | Bad ChIP (antibody, fragmentation, depth); peaks called on noise | Re-validate antibody with KO/KD; check fragment-size distribution; do not proceed |

## References

- Park PJ 2009 Nat Rev Genet 10:669 (foundational review)
- Landt SG et al 2012 Genome Res 22:1813 (ENCODE/modENCODE guidelines, IDR Nself rule)
- Zhang Y et al 2008 Genome Biol 9:R137 (MACS)
- Kharchenko PV et al 2008 Nat Biotechnol 26:1351 (SPP)
- Heinz S et al 2010 Mol Cell 38:576 (HOMER)
- Li Q et al 2011 Ann Appl Stat 5:1752 (IDR framework)
- Teytelman L et al 2013 PNAS 110:18602 (hyper-ChIPable regions)
- Park D et al 2013 PLoS One 8:e83506 (independent hyper-ChIPable confirmation)
- Amemiya HM et al 2019 Sci Rep 9:9354 (ENCODE blacklist v2)
- ENCODE ChIP-seq pipeline v2.1.6 (github.com/ENCODE-DCC/chip-seq-pipeline)
- Shpynov O & Artyomov MN 2026 Nucleic Acids Res 54:gkaf1454 (Omnipeak; benchmarks HOMER -style histone vs factor for histone marks)

## Related Skills

- chip-seq/chipseq-qc - Fragment-size diagnostic, FRiP, NSC/RSC, antibody validation
- chip-seq/cut-and-run-tag - SEACR + MACS for CUT&RUN/CUT&Tag (different QC, lower depth)
- chip-seq/spike-in-normalization - When global signal shifts expected (HDACi, BETi, EZH2i)
- chip-seq/differential-binding - DiffBind/csaw downstream of peak calling
- chip-seq/peak-annotation - Annotate peaks to genes and cCREs
- chip-seq/motif-analysis - Discover and scan binding motifs in peaks
- chip-seq/super-enhancers - Stitch H3K27ac peaks into super-enhancer calls
- atac-seq/atac-peak-calling - ATAC-specific shift/extend; no input control
- alignment-files/sam-bam-basics - Pre-call BAM filtering and deduplication
- genome-intervals/interval-arithmetic - Peak intersection and overlap

## Usage Guide

# Peak Calling - Usage Guide

## Overview

Calls ChIP-seq peaks with MACS3/MACS2, HOMER, SPP, or Genrich. Handles narrow (TF) vs broad (histone) mode selection, fragment-size modeling vs `--nomodel`, effective genome size, ENCODE-style IDR (TFs) or naive overlap (histones), aligner-specific shift caveats, and hyper-ChIPable region awareness. Cross-references chipseq-qc for pre-call validation (antibody, fragment size, FRiP) and chip-seq/cut-and-run-tag for CUT&RUN/CUT&Tag protocols (which use SEACR + MACS2 rather than MACS3 alone).

## Prerequisites

```bash
# Core peak callers
conda install -c bioconda macs3 macs2 homer samtools bedtools idr

# Phantompeakqualtools for SPP / cross-correlation fragment length
conda install -c bioconda phantompeakqualtools

# Optional: Genrich for joint replicate analysis
conda install -c bioconda genrich
```

## Quick Start

Tell the agent what to do:
- "Call peaks from chip.bam with input.bam control using ENCODE-compliant MACS2 parameters"
- "Call broad peaks for H3K27me3 with input control and naive overlap across 3 replicates"
- "Estimate fragment length via cross-correlation before peak calling"
- "Run IDR on two MACS narrowPeak replicates and apply ENCODE Nself/Nt consistency rules"
- "Call peaks on chr21-only data; adjust genome size accordingly"
- "Find peaks at the level of high-confidence consensus across MACS3 and HOMER"
- "My MACS model building failed; diagnose and rescue"

## Example Prompts

### ENCODE-compliant TF ChIP-seq
> "Run the ENCODE TF peak-calling pipeline: per-replicate MACS2 at `-p 0.01 --nomodel --shift 0 --extsize {fraglen}` with fraglen from cross-correlation, then IDR at 0.05 across true replicates with the Nself/Nt consistency check."

### Histone marks (broad)
> "Call H3K27me3 broad peaks with `--broad --broad-cutoff 0.1` for three replicates and combine via naive overlap with ≥40% reciprocal overlap."

### Narrow histone marks
> "Call H3K4me3 peaks. Use narrow mode in MACS3 and `-style histone` in HOMER (not `-style factor` despite the sharp signal; Omnipeak benchmark, Shpynov & Artyomov 2026)."

### Subset data
> "Call peaks from chr21-only ChIP-seq data with ~400k reads. Use numeric genome size, skip MACS model building, and use a narrow `--extsize 147` for the H3K4me3 mark."

### Diagnosing peak quality
> "Why are my peaks shifted ~75bp from known motif positions? Check fragment-size modeling and shift parameters."

### Hyper-ChIPable artifact suspicion
> "I'm seeing strong peaks at rRNA loci and histone gene clusters. Filter against a custom blacklist of top-1% input signal regions."

### Reconciliation
> "MACS3 and HOMER disagree on which peaks pass. Walk through the reconciliation rules from the skill and decide what to trust."

## What the Agent Will Do

1. **Pre-call validation**: confirm antibody is validated (KO/KD or peptide-array); inspect fragment-size distribution via `samtools view -f 0x2 sample.bam | awk '{print $9}'`; verify input control matches library prep / fragmentation; check FRiP, NSC, RSC if available (see chipseq-qc)
2. **Choose narrow vs broad mode** from target biology (TFs narrow; H3K27me3/H3K9me3/H3K36me3 broad; H3K4me3/H3K27ac narrow)
3. **Choose modeling strategy**: full model only for whole-genome, ≥1M treatment reads; `--nomodel --extsize` for subsets, low-depth, or ENCODE consistency
4. **Determine effective genome size**: read-length-matched value from deepTools table; numeric for subset data
5. **Call peaks per replicate** at loose threshold (`-p 1e-2` ENCODE pattern); generate signal tracks with `-B --SPMR`
6. **Replicate handling**: IDR @ 0.05 for TFs with Nself/Nt consistency rule; naive overlap with ≥40% reciprocal for histones
7. **Quality sanity check**: peak counts in expected range for target (e.g., 20-50k for H3K4me3); FRiP threshold met
8. **Hyper-ChIPable filter** if claims are made at rRNA / tRNA / histone clusters / mitochondrial DNA
9. **Output conversion**: narrowPeak/broadPeak to BED if downstream requires
10. **Document parameters** in methods (genome version + size, fragment length source, IDR threshold, blacklist version)

## Pipeline Quick Reference

### ENCODE TF pipeline

```bash
# 1. Estimate fragment length via cross-correlation
Rscript run_spp.R -c=chip.bam -savp=chip_cc.pdf -out=chip_cc.txt
FRAGLEN=$(awk -F'\t' '{print $3}' chip_cc.txt | cut -d',' -f1)

# 2. Per-replicate (loose threshold for IDR)
for i in rep1 rep2; do
    macs2 callpeak -t ${i}.bam -c input.bam \
        -f BAM -g 2.701e9 -n ${i} \
        --nomodel --shift 0 --extsize $FRAGLEN \
        --keep-dup all -B --SPMR -p 1e-2
done

# 3. IDR across true replicates
sort -k8,8nr rep1_peaks.narrowPeak > rep1.sorted
sort -k8,8nr rep2_peaks.narrowPeak > rep2.sorted
idr --samples rep1.sorted rep2.sorted \
    --input-file-type narrowPeak --rank p.value \
    --idr-threshold 0.05 --output-file true_reps.idr --plot
```

### ENCODE histone pipeline (broad)

```bash
# Per-replicate broad peaks
for i in rep1 rep2 rep3; do
    macs2 callpeak -t ${i}.bam -c input.bam \
        -f BAM -g 2.701e9 -n ${i} \
        --broad --broad-cutoff 0.1 \
        --nomodel --shift 0 --extsize $FRAGLEN \
        --keep-dup all -B --SPMR -p 1e-2
done

# Naive overlap (≥40% reciprocal, present in ≥2 reps)
bedtools intersect -a rep1_peaks.broadPeak -b rep2_peaks.broadPeak -f 0.40 -r -u > tmp12.bed
bedtools intersect -a tmp12.bed -b rep3_peaks.broadPeak -f 0.40 -r -u > naive_overlap.bed
```

## Troubleshooting

### Model building fails

MACS2/3 needs ≥100 paired plus/minus enrichment regions within `--mfold` (default `[5, 50]`). Causes:
- Single-chromosome or targeted data -> use `--nomodel`
- Low read count (<500k) -> use `--nomodel`
- Sparse enrichment -> widen with `--mfold 3 50` first, then fall back to `--nomodel`

Always inspect `<sample>_model.r` plot; silent model failure produces wrong fragment size.

### Zero peaks called

- Wrong genome size on subset data (`hs` on chr21 inflates lambda 60×) -> use numeric `-g`
- Wrong `-f` flag (BAM vs BAMPE vs BED) -> match input file type
- Swapped treatment / control -> verify `-t` is enriched sample
- Library too shallow -> check sequenced read count; minimum ~10M unique mapped for TFs, 20M+ for broad marks

### Peak count >> 500k

- Did not deduplicate -> `samtools view -F 1804 -q 30` filter pre-call
- chrM reads dominate -> remove chrM from BAM before calling
- `-q` too loose -> tighten to `-q 0.01`
- Hyper-ChIPable artifacts -> build custom blacklist from top-1% input signal

### Peaks shifted from motif by ~75 bp

- `--shift` not set with `-f BAM` -> add `--shift 0 --extsize {fraglen}`
- Cross-correlation fraglen wrong -> inspect `_cc.txt` and verify against `predictd` output
- Aligner pre-applied shift (chromap) -> drop downstream shift OR use `--no-correction`

### IDR returns 0 reproducible peaks

- Sorted by wrong column -> use `sort -k8,8nr` (p-value descending)
- Library size imbalance >2× -> pseudoreplicate IDR will fail Nself/Nt rule; rebalance via downsampling or re-do shallow rep
- One replicate is bad -> check per-rep FRiP, NSC, RSC; do not average

### FRiP < 1%

This is a hard fail. Re-validate the antibody (KO/KD control), check fragment-size distribution, confirm input control matches. Proceeding with low-FRiP data wastes downstream effort.

## Output Files

| File | Description |
|------|-------------|
| `*_peaks.narrowPeak` | BED6+4: chr, start, end, name, score, strand, signalValue, -log10(p), -log10(q), summit offset |
| `*_peaks.broadPeak` | BED6+3: broad region coordinates without summit |
| `*_summits.bed` | Per-peak summit positions (narrow only) |
| `*_model.r` | R script for fragment-size model visualization (inspect this!) |
| `*_treat_pileup.bdg` | Treatment signal (with `-B`); pileup of fragments |
| `*_control_lambda.bdg` | Control signal (with `-B`); local lambda estimate |

Convert narrowPeak to BED: `cut -f1-5 peaks.narrowPeak > peaks.bed`. For browser viewing: `sort -k1,1 -k2,2n peaks_treat_pileup.bdg | bedGraphToBigWig - chrom.sizes peaks.bw`.

## Tips

- ENCODE pattern uses `--keep-dup all` because deduplication happens upstream during BAM filtering. If skipping the ENCODE filter, set `--keep-dup auto` and accept MACS's binomial p-value estimate.
- `-p 1e-2` is intentionally loose for ENCODE; IDR (TF) or naive overlap (histone) tightens downstream. Single-replicate workflows should use `-q 0.05` or `-q 0.01` instead.
- For HOMER, ALWAYS use `-style histone` for histone marks (including narrow H3K4me3, H3K27ac per the Omnipeak benchmark, Shpynov & Artyomov 2026). Reserve `-style factor` for TFs.
- Effective genome size matters: use deepTools `effectiveGenomeSize` table read-length-matched value, not `hs`/`mm` shorthand.
- For paired-end ChIP, `-f BAMPE` uses actual fragment spans (good for histones); `-f BAM --shift 0 --extsize {fraglen}` is the ENCODE TF pattern.
- TFs and most histone marks need 20-25M unique mapped reads per replicate (ENCODE 2012 standard); H3K27me3/H3K9me3 need 40-60M for adequate broad-domain detection.
- Always document: aligner version, genome assembly + effective size, fragment length source, peak caller version + parameters, IDR/overlap threshold, blacklist version. Reviewers ask.

## Related Skills

- chip-seq/chipseq-qc - FRiP, NSC, RSC, library complexity, antibody validation
- chip-seq/cut-and-run-tag - CUT&RUN/CUT&Tag protocols (different caller choice, lower depth)
- chip-seq/spike-in-normalization - When global signal shifts expected (HDACi, BETi, EZH2i)
- chip-seq/differential-binding - DiffBind/csaw downstream
- chip-seq/peak-annotation - Annotate to genes and ENCODE cCREs
- chip-seq/motif-analysis - Motif discovery on peak sequences
- chip-seq/super-enhancers - Stitch H3K27ac peaks for SE calls
- atac-seq/atac-peak-calling - ATAC-specific Tn5 shift; no input control
- alignment-files/sam-bam-basics - Pre-call BAM filtering
- alignment-files/duplicate-handling - MarkDuplicates before peak calling

## Bundled Files

- `chip-seq--peak-calling--examples--macs3_peak_calling.sh` — copied from `examples/macs3_peak_calling.sh`
