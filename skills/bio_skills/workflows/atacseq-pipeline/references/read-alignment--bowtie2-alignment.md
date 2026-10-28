# bio-read-alignment-bowtie2-alignment

> Bundled component reference for `read-alignment/bowtie2-alignment` (original source: `skills/bio_skills/read-alignment/bowtie2-alignment`).

Aligns DNA short reads to a reference with Bowtie2, choosing end-to-end (whole read must align) vs local (soft-clip read ends) mode and a sensitivity preset; the de-facto aligner for ChIP-seq, ATAC-seq, and CUT&RUN, where fragment-geometry flags (--no-mixed, --no-discordant, --dovetail, -X) and a tool-appropriate MAPQ filter feed the peak caller. Use when aligning ChIP/ATAC/CUT&RUN reads, when read ends are adapter-contaminated and need soft-clipping, or when a tunable sensitivity/speed preset is wanted. DNA variant calling prefers bwa-alignment; RNA spliced alignment is star-alignment/hisat2-alignment; the QC gate and cross-tool MAPQ scale are alignment-files; peak calling is chip-seq/atac-seq; bisulfite uses methylation-analysis/bismark-alignment.

## Instructions

## Version Compatibility

Reference examples tested with: bowtie2 2.5+, samtools 1.19+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Bowtie2 Alignment -- End-to-End vs Local and the Fragment-Geometry Flags Are the Whole Decision

**"Align my ChIP-seq / ATAC-seq reads"** -> Map short reads with Bowtie2, choosing whether the entire read must align (end-to-end) or read ends may be soft-clipped (local), and which fragment-geometry flags to set -- because for peak assays the mode, the preset, and the --no-mixed/--dovetail/-X flags determine the fragment coordinates the peak caller actually sees.
- CLI: `bowtie2 -p 8 -x index -1 R1.fq.gz -2 R2.fq.gz | samtools sort -o aligned.bam -`

Scope: DNA short-read mapping with Bowtie2 and the mode/preset/geometry choices that matter for ChIP/ATAC/CUT&RUN. Contig naming, the QC gate, and the cross-tool MAPQ scale -> alignment-files (bam-statistics / sam-bam-basics). Peak calling and the ATAC Tn5 cut-site shift -> chip-seq, atac-seq. BAM sort/dedup/stats -> alignment-files. Read trimming -> read-qc. OUT OF SCOPE: DNA variant calling (prefer bwa-alignment), RNA (star-alignment/hisat2-alignment), bisulfite (methylation-analysis/bismark-alignment -- Bismark wraps Bowtie2 internally, do not call Bowtie2 directly for WGBS).

## The Single Most Important Modern Insight

1. **End-to-end (default) vs --local is a biology decision about whether the full read must align.** End-to-end forces the entire read to match (best score 0, no soft-clipping) -- correct for clean genomic DNA. `--local` soft-clips untrustworthy read ends to maximize score (positive match bonus) -- correct when read ends are junk: adapter read-through, the short fragments and frequent adapter contamination of ATAC-seq, or amplicon primer ends. Using end-to-end on adapter-contaminated reads mis-penalizes the good core and depresses the alignment rate; the fix is to trim first or use `--local`.
2. **Bowtie2 MAPQ is a different scale from BWA and caps low.** It is AS/XS-driven and discrete, capping at 42 in end-to-end mode and 44 in local mode -- it never reaches BWA's 60. A `MAPQ >= 30` filter (the ENCODE ChIP/ATAC convention to drop multimappers) is fine, but a BWA-style `MAPQ >= 60` "uniquely mapped" filter copied from a DNA-variant pipeline discards every Bowtie2 read. Always tune the MAPQ threshold to the aligner -- see alignment-files/sam-bam-basics for the full cross-tool table.
3. **For peak assays, the fragment-geometry flags set the coordinates the peak caller consumes.** ChIP/ATAC interpret signal at the fragment level (summits, fragment midpoints, nucleosome spacing), so a singleton ("mixed") or geometrically inconsistent (discordant) alignment injects a fragment with undefined length/position. `--no-mixed --no-discordant` restrict to concordant proper pairs; `-X 2000` widens the allowed fragment length for ATAC's nucleosome-spanning fragments; `--dovetail` lets short-fragment pairs whose mates extend past each other still count as concordant (by default such pairs are not concordant and are dropped once `--no-mixed`/`--no-discordant` are set). These flags, not the core alignment, are what make the downstream peak set correct.

## Tool Taxonomy

| Mode / tool | Citation | Mechanism / role | When |
|-------------|----------|------------------|------|
| Bowtie2 `--end-to-end` (default) | Langmead & Salzberg 2012 Nat Methods 9:357 | whole read must align; no soft-clipping; scores <= 0 | clean genomic DNA, ChIP-seq on trimmed reads |
| Bowtie2 `--local` | Langmead & Salzberg 2012 | soft-clips read ends; positive match bonus | adapter read-through, ATAC-seq, amplicon ends |
| Sensitivity presets | Langmead & Salzberg 2012 | preset expansions of -D/-R/-N/-L/-i | trade speed vs sensitivity predictably |
| bwa-mem2 | Vasimuddin 2019 IEEE IPDPS | seed-and-extend; ALT/decoy-aware | DNA variant calling instead (route OUT) -> bwa-alignment |
| Bismark (wraps Bowtie2) | Krueger & Andrews 2011 Bioinformatics 27:1571 | 3-letter C->T-aware mapping engine | bisulfite/WGBS (route OUT) -> methylation-analysis/bismark-alignment |
| STAR / HISAT2 | -- | splice-aware (route OUT) | any RNA library -> star-alignment, hisat2-alignment |

## Decision Tree by Scenario

| Scenario | Recommended | Why |
|----------|-------------|-----|
| ChIP-seq, trimmed reads | `--very-sensitive --no-mixed --no-discordant`, end-to-end, then `-q 30` | clean reads align fully; drop singletons/discordants and multimappers for peak calling |
| CUT&RUN / CUT&Tag | `--very-sensitive --local --dovetail --no-mixed --no-discordant -I 10 -X 700` | sub-nucleosomal short fragments (like ATAC); the E. coli carry-over reads are the spike-in normalizer, so align them (do not discard as contamination) -> chip-seq |
| ATAC-seq | `--very-sensitive --local --dovetail -X 2000 --no-mixed --no-discordant` | soft-clip adapter read-through; admit nucleosome-spanning and dovetailed short fragments |
| Reads with adapter read-through (untrimmed) | `--local` (or trim first) | end-to-end mis-penalizes contaminated ends |
| Need maximum sensitivity on divergent data | `--very-sensitive` (or `-N 1`) | more seed-extension attempts / a seed mismatch allowed |
| Multi-mapping analysis | `-k <N>` or `-a` | report multiple/all alignments (MAPQ unreliable in -k mode) |
| DNA variant calling | route OUT to bwa-alignment | bwa-mem2 is the variant-calling community default |
| RNA-seq | route OUT to star-alignment / hisat2-alignment | spliced reads need an N-CIGAR aligner |

Default when uncertain: `--very-sensitive` end-to-end with `--no-mixed --no-discordant` for ChIP; switch to `--local --dovetail -X 2000` for ATAC; filter `-q 30` to drop multimappers.

## Build Index

```bash
bowtie2-build --threads 8 reference.fa reference_index
# emits reference_index.{1,2,3,4}.bt2 and .rev.{1,2}.bt2. Pass the BASENAME (reference_index) to -x, NOT a file.
```

## Basic Alignment

```bash
# Paired-end, streamed to a sorted BAM. Bowtie2 prints the alignment summary to stderr.
bowtie2 -p 8 -x reference_index -1 reads_1.fq.gz -2 reads_2.fq.gz 2> align.log | \
    samtools sort -@ 4 -o aligned.sorted.bam -
samtools index aligned.sorted.bam
# single-end: -U reads.fq.gz instead of -1/-2.
```

## ChIP-seq

```bash
bowtie2 -p 8 --very-sensitive --no-mixed --no-discordant \
    --rg-id sample1 --rg SM:sample1 --rg PL:ILLUMINA --rg LB:lib1 \
    -x reference_index -1 chip_1.fq.gz -2 chip_2.fq.gz 2> chip.log | \
    samtools view -bS -q 30 -F 1804 - | \
    samtools sort -@ 4 -o chip.bam -
# -q 30 drops multimappers (Bowtie2 scale: max 42 e2e); -F 1804 removes unmapped/secondary/dup/QC-fail.
```

## ATAC-seq

```bash
# Local mode + dovetail + wide -X for adapter read-through and nucleosome-spanning short fragments.
bowtie2 -p 8 --very-sensitive --local --dovetail -X 2000 --no-mixed --no-discordant \
    -x reference_index -1 atac_1.fq.gz -2 atac_2.fq.gz 2> atac.log | \
    samtools view -bS -q 30 -F 1804 - | \
    samtools sort -@ 4 -o atac.bam -
# The Tn5 +4/-5 cut-site shift is a DOWNSTREAM signal-track transform, not done here -> atac-seq.
```

## Sensitivity Presets (end-to-end; the preset IS the speed/sensitivity decision)

```bash
bowtie2 --very-fast       -x index -1 r1.fq -2 r2.fq    # -D 5  -R 1 -N 0 -L 22 -i S,0,2.50
bowtie2 --sensitive       -x index -1 r1.fq -2 r2.fq    # -D 15 -R 2 -N 0 -L 22 -i S,1,1.15  (DEFAULT)
bowtie2 --very-sensitive  -x index -1 r1.fq -2 r2.fq    # -D 20 -R 3 -N 0 -L 20 -i S,1,0.50
# Append -local for the local-mode presets (e.g. --very-sensitive-local). Higher -D/-R/shorter -L = more sensitive, slower.
```

## Multi-mapping and Unmapped Output

```bash
bowtie2 -k 5  -x index -1 r1.fq -2 r2.fq -S out.sam     # up to 5 alignments/read (MAPQ unreliable in -k)
bowtie2 -a    -x index -1 r1.fq -2 r2.fq -S out.sam     # ALL alignments (slow on repetitive genomes)
bowtie2 --un-conc-gz unmapped_%.fq.gz -x index -1 r1.fq.gz -2 r2.fq.gz -S out.sam  # save unaligned pairs
```

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| -x | -- | index BASENAME (not a filename) |
| -1 / -2 / -U | -- | paired / single-end reads |
| --end-to-end / --local | end-to-end | whole-read vs soft-clipped alignment |
| -I / -X | 0 / 500 | min / max fragment length for a concordant pair |
| --no-mixed / --no-discordant | off | suppress singleton / discordant alignments |
| --dovetail | off | treat mate-overrun pairs as concordant (short-fragment ATAC) |
| -N | 0 | mismatches allowed in a seed (0 or 1; 1 is slower, more sensitive) |
| -L | 22 (e2e) / 20 (local) | seed length |
| -k / -a | off | report up to k / all alignments |
| --rg-id / --rg | -- | read-group id / fields |

## Per-Method Failure Modes

### End-to-end on adapter-contaminated reads
**Trigger:** untrimmed reads with adapter read-through aligned in default end-to-end mode. **Mechanism:** the contaminated 3' end forces mismatches the whole-read alignment cannot escape. **Symptom:** depressed alignment rate, lost reads at fragment ends. **Fix:** trim first (-> read-qc) or use `--local` to soft-clip the junk ends.

### MAPQ filter copied from a BWA pipeline
**Trigger:** a `MAPQ >= 60` "uniquely mapped" filter applied to Bowtie2 output. **Mechanism:** Bowtie2 caps at 42 (e2e) / 44 (local). **Symptom:** an empty BAM. **Fix:** use a tool-appropriate threshold (`-q 30` drops multimappers) -> alignment-files/sam-bam-basics.

### ATAC pairs flagged discordant
**Trigger:** ATAC alignment without `--dovetail` (and a too-tight `-X`). **Mechanism:** very short fragments produce mates that extend past each other, which default Bowtie2 does not count as concordant. **Symptom:** many real short-fragment pairs dropped by a `--no-mixed`/`--no-discordant` filter. **Fix:** add `--dovetail` and widen `-X 2000`.

### -x given a filename
**Trigger:** `-x reference_index.1.bt2` (a file) instead of the basename. **Mechanism:** `-x` expects the index basename. **Symptom:** "Could not locate a Bowtie index" error. **Fix:** pass the basename (`-x reference_index`).

### Calling Bowtie2 directly for bisulfite data
**Trigger:** aligning WGBS reads with plain Bowtie2. **Mechanism:** bisulfite converts C->T, breaking 4-letter matching. **Symptom:** very low alignment rate, strand-biased mismatches. **Fix:** use Bismark, which wraps Bowtie2 with C->T-aware mapping -> methylation-analysis/bismark-alignment.

## Quantitative Thresholds

| Threshold | Source | Rationale |
|-----------|--------|-----------|
| MAPQ cap 42 (end-to-end) / 44 (local) | Bowtie2 source (unique.h) | the scale never reaches BWA's 60; tune filters per aligner |
| `-q 30` for ChIP/ATAC | ENCODE peak-assay convention | drops multimappers from repeats before peak calling |
| -X 500 default, -X 2000 for ATAC | Bowtie2 manual | ATAC fragments span nucleosomes; the default cap flags them discordant |
| default preset `--sensitive` (-D15 -R2 -N0 -L22) | Bowtie2 manual | balanced speed/sensitivity; `--very-sensitive` for divergent/peak data |
| -F 1804 in ChIP filtering | ENCODE convention | removes unmapped + mate-unmapped + secondary + duplicate + QC-fail |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| "Could not locate a Bowtie index" | `-x` given a file, not the basename | pass the index basename to `-x` |
| Empty BAM after MAPQ filter | BWA-style `-q 60` on a 42/44-capped scale | use `-q 30` (Bowtie2 scale) -> alignment-files/sam-bam-basics |
| Low alignment rate | adapter read-through, wrong reference, contamination | trim (-> read-qc) or `--local`; verify the reference; confirm species -> read-qc/contamination-screening |
| Many ATAC pairs dropped as discordant | missing `--dovetail`, too-tight `-X` | add `--dovetail -X 2000` |
| Very low rate on bisulfite reads | plain Bowtie2 on WGBS | use Bismark -> methylation-analysis/bismark-alignment |

## References

- Langmead B, Salzberg SL. 2012. Fast gapped-read alignment with Bowtie 2. *Nat Methods* 9:357-359.
- Langmead B, Trapnell C, Pop M, Salzberg SL. 2009. Ultrafast and memory-efficient alignment of short DNA sequences to the human genome. *Genome Biol* 10:R25.
- Krueger F, Andrews SR. 2011. Bismark: a flexible aligner and methylation caller for Bisulfite-Seq applications. *Bioinformatics* 27:1571-1572.
- Vasimuddin M, Misra S, Li H, Aluru S. 2019. Efficient architecture-aware acceleration of BWA-MEM for multicore systems. *IEEE IPDPS* 2019:314-324.

## Related Skills

- bwa-alignment - DNA variant-calling alignment with bwa-mem2 (ALT/decoy-aware)
- star-alignment - RNA splice-aware alignment (when reads cross junctions)
- read-qc/fastp-workflow - Trim adapters before end-to-end alignment
- alignment-files/duplicate-handling - Mark/remove duplicates after alignment
- alignment-files/sam-bam-basics - The cross-tool MAPQ scale, SAM flags, CIGAR
- alignment-files/bam-statistics - flagstat/idxstats QC gate; what a high mapping rate hides
- chip-seq/peak-calling - Call peaks from ChIP/CUT&RUN BAMs
- atac-seq/atac-peak-calling - ATAC peak calling and the Tn5 cut-site shift
- methylation-analysis/bismark-alignment - Bisulfite alignment (wraps Bowtie2)

## Usage Guide

# Bowtie2 Alignment - Usage Guide

## Overview

Bowtie2 is a fast, memory-efficient short-read aligner whose defining choice is end-to-end (the whole read must align) vs local (read ends may be soft-clipped) mode. It is the de-facto aligner for ChIP-seq, ATAC-seq, and CUT&RUN, and it is the engine Bismark wraps for bisulfite data. For peak assays the alignment itself matters less than the mode, the sensitivity preset, and the fragment-geometry flags (--no-mixed, --no-discordant, --dovetail, -X) that determine the fragment coordinates the peak caller consumes -- this skill emphasizes those.

## Prerequisites

```bash
conda install -c bioconda bowtie2 samtools
```

- A Bowtie2 index (built with `bowtie2-build`) or a prebuilt index; pass the basename to `-x`.
- For ChIP/ATAC, decide whether reads are trimmed (end-to-end) or carry adapter read-through (local) before choosing the mode.

## Quick Start

Tell your AI agent what you want to do:
- "Align my ChIP-seq reads with Bowtie2 and filter multimappers"
- "Build a Bowtie2 index for my reference genome"
- "Align ATAC-seq reads with the right fragment and soft-clipping settings"
- "Choose end-to-end vs local mode for my data and explain why"
- "Report up to 5 alignments per read for a repetitive region"

## Example Prompts

### ChIP-seq
> "Align my paired-end ChIP-seq reads with high sensitivity, keep only concordant proper pairs, and filter to MAPQ >= 30 before peak calling."

### ATAC-seq
> "Align ATAC-seq reads allowing fragments up to 2 kb and soft-clipping adapter read-through, and tell me which flags handle the short dovetailed fragments."

### Mode choice
> "My reads have adapter contamination at the 3' end and a low alignment rate in end-to-end mode -- should I trim or switch to local mode?"

### Multi-mapping
> "Align reads and report up to 5 alignments per read for a repetitive region, and explain why MAPQ is unreliable in -k mode."

## What the Agent Will Do

1. Build the index with `bowtie2-build` if needed, and pass the basename (not a filename) to `-x`.
2. Choose end-to-end vs local mode from the data (trimmed clean DNA vs adapter-contaminated/ATAC) and a sensitivity preset.
3. Set the fragment-geometry flags for the assay: `--no-mixed --no-discordant` for ChIP, plus `--local --dovetail -X 2000` for ATAC.
4. Filter to a Bowtie2-appropriate MAPQ (`-q 30`, not a BWA-style `-q 60`) and a flag mask (`-F 1804`) before peak calling.
5. Add read groups (`--rg-id`/`--rg`) and stream to a sorted, indexed BAM.
6. Route peak calling and the ATAC Tn5 cut-site shift to the chip-seq / atac-seq categories, and the QC gate to alignment-files/bam-statistics.

## When to Use Bowtie2 vs bwa-mem2

| Use case | Bowtie2 | bwa-mem2 |
|----------|---------|----------|
| ChIP-seq / CUT&RUN | preferred (ENCODE standard) | works |
| ATAC-seq | preferred (local + dovetail) | works |
| DNA variant calling (WGS/WES) | not the community default | preferred |
| RNA-seq | no (use STAR/HISAT2) | no (use STAR/HISAT2) |
| Soft-clipping adapter-contaminated ends | yes (`--local`) | yes (`-L` tuning) |

## Tips

- Choose the mode from the data: end-to-end for clean trimmed DNA, `--local` for adapter read-through or ATAC.
- Never copy a BWA `MAPQ >= 60` filter to Bowtie2 output -- the scale caps at 42 (end-to-end) / 44 (local); use `-q 30`.
- For ATAC, add `--dovetail` and `-X 2000` or real short-fragment pairs get flagged discordant and dropped.
- Pass the index basename to `-x`, not a `.bt2` file.
- Bowtie2 writes its alignment summary to stderr -- capture it (`2> align.log`) for QC and MultiQC aggregation.
- The Tn5 +4/-5 cut-site shift for ATAC is a downstream signal-track transform, not an alignment flag; route it to the atac-seq category.

## Related Skills

- bwa-alignment - DNA variant-calling alignment with bwa-mem2 (ALT/decoy-aware)
- star-alignment - RNA splice-aware alignment (when reads cross junctions)
- read-qc/fastp-workflow - Trim adapters before end-to-end alignment
- alignment-files/duplicate-handling - Mark/remove duplicates after alignment
- alignment-files/bam-statistics - flagstat/idxstats QC gate; the cross-tool MAPQ scale via sam-bam-basics
- chip-seq/peak-calling - Call peaks from ChIP/CUT&RUN BAMs
- atac-seq/atac-peak-calling - ATAC peak calling and the Tn5 cut-site shift
- methylation-analysis/bismark-alignment - Bisulfite alignment (wraps Bowtie2)

## Bundled Files

- `read-alignment--bowtie2-alignment--examples--align_bowtie2.sh` — copied from `examples/align_bowtie2.sh`
