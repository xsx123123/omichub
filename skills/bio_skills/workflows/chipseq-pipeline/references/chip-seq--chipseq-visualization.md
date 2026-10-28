# bio-chipseq-visualization

> Bundled component reference for `chip-seq/chipseq-visualization` (original source: `skills/bio_skills/chip-seq/chipseq-visualization`).

Visualizes ChIP-seq data using deepTools (computeMatrix, plotHeatmap, plotProfile, bamCoverage, bamCompare), pyGenomeTracks (modern INI-driven track plots), Gviz (R browser-style), EnrichedHeatmap (ComplexHeatmap-based), ChIPseeker tag heatmaps, and IGV batch screenshots. Handles bigWig normalization choices (CPM, BPM, RPGC, spike-in scaled), bamCompare operations (log2 ratio, subtract) with SES scaling, k-means clustering of heatmaps for biological subgrouping, and spike-in-scaled tracks for global-shift experiments. Use when generating publication-quality ChIP-seq signal heatmaps, profile plots, genome-browser tracks, or comparing samples visually.

## Instructions

## Version Compatibility

Reference examples tested with: deepTools 3.5+, pyGenomeTracks 3.9+, Gviz 1.46+, EnrichedHeatmap 1.32+, ChIPseeker 1.38+, IGV 2.17+, samtools 1.19+, bedtools 2.31+.

# ChIP-seq Visualization

**"Visualize ChIP-seq signal around features of interest"** -> Generate normalized signal tracks (bigWig), heatmaps centered on TSS/peaks, average profile plots, and genome-browser views — with normalization that supports the biological claim (within-sample vs cross-sample vs spike-in scaled).

- CLI (production): deepTools `bamCoverage` -> `computeMatrix` -> `plotHeatmap` / `plotProfile`
- CLI (config-driven tracks): pyGenomeTracks (replaces Gviz for many use cases)
- R (publication): Gviz, EnrichedHeatmap, ChIPseeker tag heatmaps
- GUI: IGV with batch scripts for reproducible screenshots

The single most consequential choice is **bigWig normalization** — it determines whether visual comparison reflects biology. Get this right before generating any heatmap or browser view.

## bigWig Normalization Decision Tree

| Goal | Method | When to use |
|------|--------|------------|
| Within-sample profile of a single ChIP | `--normalizeUsing CPM` | Standard; reads per million; comparable within one library |
| Within-sample, length-aware | `--normalizeUsing BPM` | TPM-analog; useful for variable-width regions; less common for ChIP-seq |
| Cross-sample with equal effective depth | `--normalizeUsing RPGC --effectiveGenomeSize <N>` | "1x genome coverage" — assumes equal sequencing genome-wide; ENCODE convention |
| Cross-condition with global signal change | `--scaleFactor <spike_in_derived>` (skip `--normalizeUsing`) | HDACi / BETi / EZH2i; see chip-seq/spike-in-normalization |
| ChIP vs input ratio | `bamCompare --operation log2` | Visualize enrichment over input |
| ChIP vs input control-subtracted | `bamCompare --operation subtract` | Absolute signal above background |
| ChIP vs input SES-corrected | `bamCompare --scaleFactorsMethod SES --operation log2` | More robust to library size; uses signal-extraction-scaling |

**ENCODE convention:** RPGC with read-length-matched effective genome size. For visual comparison of treatment vs control on a fold-change biology, log2 bamCompare against shared input.

**Spike-in scaled tracks (the right way):**

```bash
# Compute scale factor from spike-in reads (ChIP-Rx Drosophila or CUT&RUN E. coli)
SCALE=$(echo "scale=6; 1.0 / $SPIKE_IN_READS_M" | bc)  # 1 per million spike reads
bamCoverage -b chip.bam -o chip.bw --scaleFactor $SCALE --binSize 10
# DO NOT also pass --normalizeUsing; deepTools multiplies the two factors, reintroducing depth normalization
```

## deepTools Workflow

### bigWig generation

```bash
# Standard within-sample (CPM)
bamCoverage -b chip.bam -o chip.bw \
    --normalizeUsing CPM --binSize 10 \
    --extendReads 200 --numberOfProcessors 8

# Cross-sample at 1x genome coverage (ENCODE)
bamCoverage -b chip.bam -o chip.bw \
    --normalizeUsing RPGC --effectiveGenomeSize 2701495761 \
    --binSize 10 --extendReads 200

# ChIP vs Input log2 ratio (visualization of enrichment)
bamCompare -b1 chip.bam -b2 input.bam -o chip_vs_input.bw \
    --operation log2 --binSize 50 --extendReads 200 \
    --pseudocount 1 --skipZeroOverZero
```

### Signal matrix and heatmap (reference-point: TSS / peak summit)

```bash
# Compute matrix centered on TSS
computeMatrix reference-point \
    --referencePoint TSS \
    -b 3000 -a 3000 \
    -R genes.bed \
    -S chip.bw input.bw \
    -o matrix.gz \
    --outFileSortedRegions sorted_regions.bed \
    --numberOfProcessors 8 \
    --skipZeros

# Heatmap with k-means clustering (biology emerges from clusters)
plotHeatmap -m matrix.gz \
    -o heatmap.pdf \
    --kmeans 3 \
    --colorMap RdBu_r \
    --zMin -3 --zMax 3 \
    --refPointLabel TSS \
    --heatmapHeight 12 \
    --whatToShow 'heatmap and colorbar'

# Profile plot (average signal across regions)
plotProfile -m matrix.gz \
    -o profile.pdf \
    --perGroup \
    --plotTitle 'H3K4me3 around TSS'
```

### Scale-regions (gene-body scaled to common length)

```bash
computeMatrix scale-regions \
    -R genes.bed \
    -S chip.bw \
    -b 3000 -a 3000 \
    -m 5000 \
    -o matrix_genebody.gz \
    --numberOfProcessors 8

plotProfile -m matrix_genebody.gz -o genebody_profile.pdf --perGroup
```

### Sample correlation

```bash
multiBamSummary bins -b sample1.bam sample2.bam sample3.bam \
    --binSize 10000 -o results.npz \
    --numberOfProcessors 8

plotCorrelation -in results.npz \
    --corMethod spearman \
    --whatToPlot heatmap \
    --plotNumbers -o correlation.pdf \
    --outFileCorMatrix correlation.tab
# Replicates should correlate > 0.8 (narrow), > 0.6 (broad)
```

## pyGenomeTracks (Modern Browser-Style Plotting)

INI-driven, config-as-code; better than Gviz for complex layouts or pipeline integration.

```ini
# tracks.ini
[x-axis]

[chip-h3k27ac]
file = h3k27ac.bw
color = darkblue
height = 3
title = H3K27ac

[chip-h3k4me3]
file = h3k4me3.bw
color = darkred
height = 3
title = H3K4me3

[peaks-narrowpeak]
file = peaks.narrowPeak
file_type = narrow_peak
color = black
height = 0.5
title = MACS peaks

[se-bed]
file = super_enhancers.bed
color = orange
height = 0.5
title = Super-enhancers

[genes]
file = genes.gtf
color = darkgreen
prefered_name = gene_name
height = 4
```

```bash
pyGenomeTracks --tracks tracks.ini --region chr1:1000000-1500000 -o region.pdf
```

For pipeline-driven figure generation across multiple regions, pyGenomeTracks is easier to script than Gviz. For one-off publication figures with complex annotation, Gviz remains useful.

## R: Gviz and EnrichedHeatmap

```r
library(Gviz)
library(GenomicRanges)
library(TxDb.Hsapiens.UCSC.hg38.knownGene)

chr <- 'chr1'; start <- 1e6; end <- 1.1e6
itrack <- IdeogramTrack(genome = 'hg38', chromosome = chr)
gtrack <- GenomeAxisTrack()
dtrack <- DataTrack(range = 'sample.bw', genome = 'hg38',
                     type = 'histogram', name = 'ChIP', col.histogram = 'darkblue')
grtrack <- GeneRegionTrack(TxDb.Hsapiens.UCSC.hg38.knownGene,
                            genome = 'hg38', chromosome = chr, name = 'Genes')
plotTracks(list(itrack, gtrack, dtrack, grtrack), from = start, to = end, chromosome = chr)
```

```r
library(EnrichedHeatmap)
library(rtracklayer)

# Normalize bigWig signal to a matrix around target sites
signal <- import('sample.bw')
tss <- promoters(txdb, upstream = 0, downstream = 1)
mat <- normalizeToMatrix(signal, tss, extend = 3000, mean_mode = 'w0', w = 50)

# Heatmap with customization
EnrichedHeatmap(mat, name = 'Signal', col = c('white', 'red'),
                top_annotation = HeatmapAnnotation(lines = anno_enriched()))
```

## ChIPseeker Tag Heatmap (R)

```r
library(ChIPseeker)
library(TxDb.Hsapiens.UCSC.hg38.knownGene)

peaks <- readPeakFile('peaks.narrowPeak')
promoter <- getPromoters(TxDb = TxDb.Hsapiens.UCSC.hg38.knownGene,
                          upstream = 3000, downstream = 3000)
tagMatrix <- getTagMatrix(peaks, windows = promoter)

# Tag heatmap and average profile
# tagHeatmap in ChIPseeker >= 1.36 takes palette (RColorBrewer name), not xlim/color;
# xlim is read from the tagMatrix window. plotAvgProf still uses xlim/conf.
tagHeatmap(tagMatrix, palette = 'Reds')
plotAvgProf(tagMatrix, xlim = c(-3000, 3000), conf = 0.95,
             xlab = 'Distance from TSS (bp)', ylab = 'Peak density')
```

## IGV Batch Scripts

```bash
# IGV batch script for reproducible screenshots
cat > igv.batch << 'EOF'
new
genome hg38
load chip.bw
load peaks.bed
load super_enhancers.bed
goto chr1:1000000-1100000
snapshot region1.png
goto chr2:50000000-51000000
snapshot region2.png
exit
EOF

igv.sh -b igv.batch
```

## Per-Tool Failure Modes

### bamCoverage -- `--normalizeUsing` and `--scaleFactor` conflict

**Trigger:** Passing both `--normalizeUsing CPM` and `--scaleFactor X`.

**Mechanism:** deepTools multiplies the `--scaleFactor` value by the factor computed from `--normalizeUsing`, so passing both compounds them and reintroduces library-depth normalization on top of the spike-in factor.

**Symptom:** Spike-in scaling appears to have no effect; tracks look like CPM.

**Fix:** Use ONE — `--scaleFactor` alone for spike-in; `--normalizeUsing` alone otherwise. Never both.

### bamCompare -- log2 with zeros produces -Inf

**Trigger:** `bamCompare --operation log2` without pseudocount; many bins have zero reads.

**Mechanism:** log2(0/x) = -Inf; downstream tools (plotHeatmap) may color these as NaN or fail.

**Fix:** Add `--pseudocount 1` to both samples; or use `--skipZeroOverZero` to skip bins with zero in both samples.

### computeMatrix -- Stranded bigWig vs unstranded reference points

**Trigger:** Using stranded bigWigs (separate plus/minus) with `reference-point` mode on a BED without strand info.

**Mechanism:** computeMatrix doesn't auto-detect strand; signal is plotted in genomic-strand orientation, breaking TSS-centered plots.

**Fix:** Use unstranded merged bigWig OR ensure BED has strand column 6.

### plotHeatmap `--kmeans` -- Order depends on first sample only

**Trigger:** Using k-means with multiple samples and expecting consistent clustering.

**Mechanism:** k-means clusters by signal in the first `-S` bigWig only; other samples are plotted in the same row order.

**Fix:** Order samples in `-S` so the most-discriminating one is first; for combined clustering across samples, use `--hclust` or run k-means externally on combined matrix.

### Spike-in scaled bigWig -- Wrong scale factor direction

**Trigger:** Computing `scale_factor = spike_reads / 1e6` and passing to `--scaleFactor`.

**Mechanism:** deepTools multiplies signal by scaleFactor; the INVERSE is correct (sample with fewer spike reads gets larger scale factor to compensate).

**Symptom:** Treatment samples appear lower than control even when biology says higher.

**Fix:** `scale_factor = MIN(spike_reads_all_samples) / spike_reads_this_sample`. Always verify against known internal-control regions (blacklist should show no signal change post-scaling).

### Gviz / EnrichedHeatmap -- Memory failure on whole-genome bigWigs

**Trigger:** Loading a 3 GB bigWig into R as a GRanges.

**Mechanism:** Gviz loads the entire bigWig into memory for genome-wide views.

**Fix:** Use `chromosome` parameter to restrict; use `import.bw(con, which = GRanges(...))` to subset; consider pyGenomeTracks for whole-chromosome views.

### pyGenomeTracks -- INI parsing strict

**Trigger:** Custom INI keys not recognized; or section names with spaces.

**Mechanism:** pyGenomeTracks expects exact key names; case-sensitive section labels.

**Fix:** Run `make_tracks_file --trackFiles sample.bw -o tracks.ini` to generate a template; modify from there.

## Reconciliation: When Visualizations Disagree

| Pattern | Likely cause | Action |
|---------|--------------|--------|
| Heatmap shows enrichment; profile plot doesn't | Signal concentrated at few regions; profile averages them out | Both correct; heatmap shows distribution, profile shows central tendency |
| Replicate heatmaps differ at peak edges | Different normalization or stranded vs unstranded bigWigs | Verify bigWig parameters identical; use same `--normalizeUsing` |
| Spike-in scaled tracks show opposite trend from CPM | Global shift; CPM forces median to control levels | Spike-in is correct; CPM is fooled by composition |
| ChIPseeker tag heatmap differs from deepTools heatmap | ChIPseeker uses peak density; deepTools uses signal coverage | Different metrics; pick one per analysis |
| Profile plot loose-replicate band wide | Genuine biological variability OR one replicate failed | Check per-replicate metrics (chipseq-qc); don't average across failing rep |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| bigWig has all zeros | Wrong chromosome naming (chr vs no chr) | `samtools view -H bam | head` to check; convert if needed |
| computeMatrix "all regions skipped" | BED chromosome naming mismatches bigWig | Match seqlevels |
| plotHeatmap colors compressed | `--zMin/--zMax` not set; outliers dominate | Set `--zMin -3 --zMax 3` or use percentile-based |
| IGV batch hangs | `exit` command missing; IGV waits for input | Always end batch script with `exit` |
| pyGenomeTracks region out of range | Region exceeds chromosome length | Verify region from `samtools view -H bam` |
| Spike-in scaled track has artifact stripes | Scale factor too extreme (>10x) | Verify spike-in reads adequate (>100k); check titration |

## References

- Ramírez F et al 2016 Nucleic Acids Res 44:W160 (deepTools)
- Lopez-Delisle L et al 2021 Bioinformatics 37:422 (pyGenomeTracks)
- Hahne F & Ivanek R 2016 Methods Mol Biol 1418:335 (Gviz)
- Gu Z et al 2018 BMC Genomics 19:234 (EnrichedHeatmap)
- Yu G et al 2015 Bioinformatics 31:2382 (ChIPseeker)
- Thorvaldsdóttir H et al 2013 Brief Bioinform 14:178 (IGV)
- ENCODE 2012 quality metrics (NSC/RSC; for cross-correlation context)

## Related Skills

- chip-seq/peak-calling - Peak files for heatmap reference regions
- chip-seq/chipseq-qc - QC plots (fingerprint, correlation) complement visualization
- chip-seq/spike-in-normalization - Spike-in-scaled bigWig generation
- chip-seq/differential-binding - Visualize differential peak signal
- chip-seq/super-enhancers - SE region visualization in tracks
- data-visualization/genome-tracks - General genome track patterns + IGV batch + pyGenomeTracks
- data-visualization/heatmaps-clustering - General heatmap conventions

## Usage Guide

# ChIP-seq Visualization - Usage Guide

## Overview

Generate ChIP-seq heatmaps, profile plots, genome-browser tracks, and sample-correlation visualizations. Covers deepTools (production), pyGenomeTracks (modern config-driven tracks), Gviz / EnrichedHeatmap / ChIPseeker (R), and IGV batch scripts. Embeds bigWig normalization decisions (CPM, BPM, RPGC, spike-in scaled), bamCompare operation choice (log2/subtract) with SES scaling, and k-means clustering of heatmaps for biological subgrouping. The most consequential choice is bigWig normalization; it determines whether visual comparison reflects biology.

## Prerequisites

```bash
conda install -c bioconda deeptools samtools bedtools pygenometracks
```

```r
BiocManager::install(c('Gviz', 'EnrichedHeatmap', 'ChIPseeker',
                       'TxDb.Hsapiens.UCSC.hg38.knownGene', 'rtracklayer'))
```

```bash
# IGV (for batch screenshots)
# Download from https://software.broadinstitute.org/software/igv/download
```

## Quick Start

Tell the agent what to do:
- "Generate spike-in-scaled bigWigs from a BAM list and Drosophila spike-in counts"
- "Create a TSS-centered heatmap with k-means clustering across 4 ChIP samples"
- "Compare ChIP signal between treatment and control with log2 bamCompare bigWig"
- "Build a pyGenomeTracks INI for chr1:1M-2M with H3K27ac, H3K4me3, MACS peaks, gene annotation"
- "Make an IGV batch script for 10 published loci to generate consistent screenshots"
- "Compute Spearman correlation between 6 replicates with multiBamSummary and plotCorrelation"
- "Why does my heatmap look identical across samples when I expect treatment-specific signal?"

## Example Prompts

### Standard heatmap + profile (TSS centered)
> "Convert chip.bam and input.bam to bigWigs with CPM normalization. Compute matrix centered on TSS (±3 kb). Generate heatmap with `--zMin -3 --zMax 3 --colorMap RdBu_r` and profile plot."

### k-means clustering for biology
> "I have H3K27ac signal at 5000 promoters. Use plotHeatmap with `--kmeans 3` to identify clusters of promoters by signal pattern. Output the cluster assignment BED."

### log2 ratio of ChIP vs Input
> "Generate a log2 ratio bigWig: bamCompare ChIP vs input with `--operation log2 --pseudocount 1 --skipZeroOverZero`. Use bin size 50."

### Spike-in scaled tracks
> "I have 120k Drosophila reads in ctrl_1 and 85k in treat_1. Compute scale factors (smallest / each) and generate spike-in-scaled bigWigs. Do NOT also pass `--normalizeUsing`."

### Cross-condition comparison
> "Build heatmaps showing H3K27ac signal at union SE regions for DMSO vs BETi. Use RPGC normalization for cross-sample comparability OR spike-in scaled if I have spike-in data."

### Genome browser views
> "Generate pyGenomeTracks figure for chr1:1500000-1700000 showing H3K27ac, H3K4me3, MACS narrowPeak, SE BED, and gene annotation."

### IGV batch
> "Create an IGV batch script to screenshot 5 specific loci with my BAM, BW, and peak files. End with `exit`."

### Diagnostic
> "My heatmap looks pancake-flat. Diagnose: is it normalization (`--zMin --zMax` not set), data quality, or wrong matrix mode?"

## What the Agent Will Do

1. **Choose normalization** based on biology:
   - Within-sample: CPM (standard) or BPM (length-aware)
   - Cross-sample comparable: RPGC with read-length-matched effective genome size
   - Cross-condition with global shifts: spike-in scaled (`--scaleFactor` alone; do not combine with `--normalizeUsing`)
   - ChIP vs input: bamCompare log2 (most common) / subtract; SES via --scaleFactorsMethod
2. **Generate bigWigs**: `bamCoverage` or `bamCompare`; extend single-end reads to fragment length; bin size 10-50 bp
3. **Compute signal matrix**: reference-point (TSS / peak summit) with `-b 3000 -a 3000`, or scale-regions for gene bodies
4. **Generate plots:**
   - Heatmaps with `--zMin/--zMax` set; `--kmeans N` for biological subgrouping
   - Profile plots with `--perGroup` for sample comparison
   - Browser tracks via pyGenomeTracks INI (recommended) or Gviz (R)
5. **Sample correlation**: `multiBamSummary bins` -> `plotCorrelation --corMethod spearman`
6. **Validate**: check that scale, normalization, and figure annotations match the biological claim
7. **Export**: PDF (publication) or PNG (presentation); pyGenomeTracks supports both
8. **Document**: normalization method + parameters, bin size, color map, z-scale, region count, kmeans settings if used

## Tips

- **Normalization choice is the single biggest decision.** Get it right before generating any heatmap.
- **Pass `--scaleFactor` alone in bamCoverage for spike-in.** deepTools multiplies it by any `--normalizeUsing` factor, so combining them reintroduces depth normalization.
- **For log2 bamCompare, always add `--pseudocount 1 --skipZeroOverZero`** to avoid -Inf in plots.
- **Set `--zMin/--zMax` explicitly.** Default ranges are outlier-driven and produce uninformative heatmaps.
- **k-means clusters by signal in the FIRST `-S` sample only.** Order samples so the most-discriminating one is first.
- **Pyramids of error: read length must match the bigWig effective genome size.** Use deepTools `effectiveGenomeSize` table for accurate RPGC.
- **For broad histone marks, use larger bin sizes (50-100 bp) and broader matrix windows (5-10 kb).**
- **pyGenomeTracks is easier to script than Gviz** for pipeline figure generation across many regions; Gviz is more flexible for one-off publication figures.
- **For spike-in scaled tracks, internal-control sanity check**: blacklist regions should show no signal change post-scaling. See chip-seq/spike-in-normalization.
- **IGV batch scripts MUST end with `exit`** or IGV hangs.

## Troubleshooting

### Heatmap looks pancake-flat

1. `--zMin/--zMax` not set; outliers dominate the color scale -> set explicit range
2. Bin size too large for signal pattern -> use 10 bp for sharp marks
3. Window too narrow for biology -> broaden `-b -a` parameters
4. Signal too low -> check FRiP, depth (see chipseq-qc)

### Spike-in scaled tracks identical to CPM tracks

`--normalizeUsing` and `--scaleFactor` both passed; deepTools multiplies the two, reintroducing depth normalization. Use `--scaleFactor` alone for spike-in.

### Profile plot shows identical curves for treatment and control

1. Wrong bigWig used (sample swap)
2. Composition-bias-driven normalization erased the difference
3. Replicate signal averaged across one good + one bad replicate

### Tracks display "no data" in pyGenomeTracks

1. Region outside chromosome bounds -> check `samtools view -H bam | head`
2. INI file path errors -> use absolute paths in `file =`
3. Chromosome naming mismatch (chr vs no chr)

### IGV batch script hangs

Missing `exit` at end; IGV waits indefinitely for next command.

### bamCompare log2 ratios show -Inf or NaN

Missing `--pseudocount 1` or `--skipZeroOverZero`. Either fix produces plottable values.

### Heatmap k-means clusters look random

k-means clusters by FIRST sample only. If the first sample has weak signal, clustering becomes noise-driven. Reorder samples so the most-discriminating one is first; or compute matrix per-sample and combine externally for joint clustering.

## Related Skills

- chip-seq/peak-calling - Peak files for reference regions
- chip-seq/chipseq-qc - Replicate correlation, fingerprint plots
- chip-seq/spike-in-normalization - Spike-in scaled bigWig generation
- chip-seq/differential-binding - Visualize differential peaks
- chip-seq/super-enhancers - Heatmaps of SE constituents
- chip-seq/peak-annotation - Annotation-aware visualization (promoter vs enhancer)
- data-visualization/genome-tracks - General genome track patterns
- data-visualization/heatmaps-clustering - Heatmap clustering conventions

## Bundled Files

- `chip-seq--chipseq-visualization--examples--chipseeker_profile.R` — copied from `examples/chipseeker_profile.R`
- `chip-seq--chipseq-visualization--examples--deeptools_heatmap.sh` — copied from `examples/deeptools_heatmap.sh`
