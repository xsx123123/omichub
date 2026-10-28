# bio-duplicate-handling

> Bundled component reference for `alignment-files/duplicate-handling` (original source: `skills/bio_skills/alignment-files/duplicate-handling`).

Mark and remove PCR/optical duplicates using samtools fixmate and markdup. Use when preparing alignments for variant calling or when duplicate reads would bias analysis.

## Instructions

## Version Compatibility

Reference examples tested with: picard 3.1+, pysam 0.22+, samtools 1.19+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Duplicate Handling

**"Remove PCR duplicates from my BAM file"** -> Mark or remove duplicate reads using the fixmate-sort-markdup pipeline to prevent duplicate bias in variant calling.
- CLI: `samtools fixmate`, `samtools markdup` (samtools)
- Python: `pysam.fixmate()`, `pysam.markdup()` (pysam)

Mark and remove PCR/optical duplicates using samtools.

## Why Remove Duplicates?

PCR duplicates are identical copies of the same original molecule, created during library preparation. They inflate coverage, bias allele frequencies, and create false positive variant calls. Optical duplicates are flowcell-proximity artifacts: on unpatterned flowcells they arise when the imaging software splits one cluster into two adjacent calls; on patterned flowcells (NovaSeq, NovaSeq X, NextSeq 1000/2000, HiSeq X/4000) the dominant source is ExAmp (exclusion-amplification) "pad-hopping", where a library molecule re-seeds a nearby nanowell.

## When to Mark Duplicates -- and When NOT To

Standard `samtools markdup` is the right tool for some assays and actively harmful for others. The decision is assay-driven:

| Assay | Standard markdup? | Recommended approach |
|-------|------------------|----------------------|
| Germline WGS / WES (PCR or PCR-free) | YES | `samtools markdup` (PCR-free still has ~0.5% optical duplicates on patterned flowcells) |
| Somatic tumor/normal (no UMI) | YES | Same |
| Exome / target capture | YES (20-50% expected) | `samtools markdup` |
| ChIP-seq | **MARK, do not remove** | Then use peak caller's auto-dup logic (`macs3 --keep-dup auto`) |
| CUT&RUN / CUT&Tag | MARK, do not remove | Same |
| ATAC-seq | YES, BEFORE Tn5 +4/-5 shift | Then shift coords for footprinting |
| Bulk RNA-seq (no UMIs) | **NO** | Duplicates are biological at highly-expressed loci; removing them biases DE proportional to expression |
| Bulk RNA-seq (with UMIs) | NO | umi_tools dedup |
| scRNA (10x, STARsolo, drop-seq) | **NO** | umi_tools dedup with CB+UB tags, or rely on Cell Ranger UMI counts |
| ctDNA / liquid biopsy / deep panel (UMI) | NO | fgbio GroupReadsByUmi -> CallDuplexConsensusReads |
| Twist / IDT / Roche UMI capture | NO | fgbio or Picard UmiAwareMarkDuplicatesWithMateCigar |
| Amplicon / hotspot panel (no UMI) | **NO** | Every read is a "duplicate" by coordinate; markdup erases the dataset. Use `samtools ampliconclip` instead -- see alignment-amplicon-clipping. |
| Amplicon / hotspot panel (UMI) | NO | fgbio consensus |
| Long-read native (ONT, PacBio HiFi unamplified) | NO | No PCR step; markdup is meaningless |
| PacBio HiFi amplicon | YES (rare) | `pbmarkdup` |
| Ancient DNA (aDNA) | YES + mapDamage | Run markdup, then mapDamage `--rescale` before variant calling |
| Microbiome 16S/ITS | NO | Read counts encode community structure |

If the BAM came from 10x Cell Ranger / STARsolo and `samtools markdup` produces a 50-95% duplicate rate, it is the wrong tool, not a bug.

## Tool Selection: markdup vs Picard vs UMI-aware

| Tool | Speed | Threading | Optical | UMI | Notes |
|------|-------|-----------|---------|-----|-------|
| `samtools markdup` | Fast | Yes | Yes (`-d`) | Limited (`--barcode-tag` exact-match) | Fast production choice (nf-core/sarek defaults to GATK MarkDuplicates) |
| `picard MarkDuplicates` | Slow | No | Yes | UmiAware variant (BETA, transcriptome bug) | GATK Best Practices reference |
| `biobambam2 bammarkduplicates2` | Fastest | Yes | Yes | No | Sanger / 1KGP pipelines |
| `samblaster` | Streaming, fast | No | Optional | No | Pipe directly from aligner; no name sort |
| `sambamba markdup` | Fast | Yes | Yes | No | Less actively maintained |
| `fgbio GroupReadsByUmi` + `CallMolecularConsensusReads` | Fast | Yes | n/a | **Best UMI tool** | Graph-based; supports duplex |
| `umi_tools dedup` | Slow | No | n/a | Yes (mature) | Reference for scRNA / bulk UMI |
| `pbmarkdup` | Fast | Yes | n/a | n/a | PacBio HiFi amplicons only |

Picard `UmiAwareMarkDuplicatesWithMateCigar` is BETA and has known bugs on transcriptome-aligned BAMs (silently keeps duplicates). Avoid for RNA-seq UMIs.

## Optical Distance Is Platform-Specific

`samtools markdup` default is `-d 0`, meaning **optical-duplicate detection is disabled by default**. Set explicitly per platform:

| Platform | `-d` value | Rationale |
|----------|-----------|-----------|
| HiSeq 2000/2500 (random) | 100 | Picard historic default |
| HiSeq 3000/4000/X (patterned) | 2500 | Patterned tile size larger |
| NovaSeq 6000 (patterned) | 2500 | Same as HiSeq X |
| NovaSeq X (10B) | 2500 | Patterned; same starting point as NovaSeq 6000 |
| NextSeq 1000/2000 (patterned) | 2500 | ExAmp duplicates span larger pixel distances |
| MiSeq, NextSeq 500/550 | 100 | Smaller / unpatterned |
| Element AVITI, MGI / DNBseq | Custom regex | Different read-name format -- supply via `--read-coords` |

```bash
samtools markdup -d 2500 -f stats.txt input.bam marked.bam

# Count optical (SQ) vs library/PCR (LB) duplicates. The dt:Z:SQ/LB tag is
# emitted automatically because -d is set (it is not produced by -t, which
# instead adds a 'do' tag carrying the original read's name).
samtools view -f 1024 marked.bam | grep -o 'dt:Z:[A-Z][A-Z]' | sort | uniq -c
```

Setting `-d 2500` on a HiSeq run does no harm. Forgetting `-d 2500` on NovaSeq systematically under-marks optical duplicates and overestimates library complexity.

## Multi-Library Pooled Marking

Without `--use-read-groups`, multi-library BAMs systematically over-mark: independent molecules from different libraries with the same coordinates get wrongly flagged as PCR duplicates. With `--use-read-groups`, RG tags must also match for two reads to be a duplicate (verify availability with `samtools markdup --help`):
```bash
samtools markdup --use-read-groups -d 2500 in.bam out.bam
```

samtools `--use-read-groups` keys on RG ID; Picard's library-aware behavior keys on the LB tag (allowing dedup across multiple lanes of the same library). For multi-lane single-library BAMs, Picard MarkDuplicates with `READ_NAME_REGEX` is closer to canonical.

## Duplicate Marking Workflow

**Goal:** Mark PCR/optical duplicates so they can be excluded from downstream variant calling and coverage analysis.

**Approach:** Name-sort, add mate tags with fixmate, coordinate-sort, then run markdup. The pipeline version avoids intermediate files.

**Reference (samtools 1.19+):**
```bash
# 1. Sort by name (required for fixmate)
samtools sort -n -o namesort.bam input.bam

# 2. Add mate information with fixmate
samtools fixmate -m namesort.bam fixmate.bam

# 3. Sort by coordinate (required for markdup)
samtools sort -o coordsort.bam fixmate.bam

# 4. Mark duplicates
samtools markdup coordsort.bam marked.bam

# 5. Index result
samtools index marked.bam
```

### Pipeline Version (Optimized)
```bash
# collate is faster than sort -n; -u/-O between piped tools skips BGZF round-trips
samtools collate -O -u input.bam tmpdir/collate | \
    samtools fixmate -m -u - - | \
    samtools sort -u -@ 4 -T tmpdir/sort - | \
    samtools markdup -@ 4 -d 2500 --use-read-groups \
        -f markdup_stats.txt - marked.bam

samtools index marked.bam
```

This is ~30% faster than `sort -n | fixmate | sort | markdup` on typical 30x WGS.

**Critical pitfall:** `samtools markdup` requires `ms` (mate score, lowercase) and `MC` (mate CIGAR) tags from `fixmate -m`. A re-sort that loses aux tags via Python round-trip silently produces a markdup output that marks almost nothing. If duplicate counts look implausibly low, verify `MC:Z:` is present in the input to markdup.

## samtools fixmate

Adds mate information required by markdup. Must be run on name-sorted BAM.

### Basic Usage
```bash
samtools fixmate namesorted.bam fixmate.bam
```

### Add Mate Score Tag (-m)
```bash
# Required for markdup to work correctly
samtools fixmate -m namesorted.bam fixmate.bam
```

### Multi-threaded
```bash
samtools fixmate -m -@ 4 namesorted.bam fixmate.bam
```

### Remove Secondary/Unmapped
```bash
samtools fixmate -r -m namesorted.bam fixmate.bam
```

## samtools markdup

Marks or removes duplicate alignments. Requires coordinate-sorted BAM with mate tags from fixmate.

### Mark Duplicates (Keep in File)
```bash
samtools markdup input.bam marked.bam
```

### Remove Duplicates
```bash
samtools markdup -r input.bam deduped.bam
```

### Output Statistics
```bash
samtools markdup -s input.bam marked.bam 2> markdup_stats.txt
```

### Optical Duplicate Distance
```bash
# Default -d 0 disables optical detection. Set per platform; see decision table above.
samtools markdup -d 2500 input.bam marked.bam   # NovaSeq / patterned
samtools markdup -d 100 input.bam marked.bam    # HiSeq / random
```

### Multi-threaded
```bash
samtools markdup -@ 4 input.bam marked.bam
```

### Write Stats to File
```bash
samtools markdup -f stats.txt input.bam marked.bam
```

## Duplicate Statistics

### Check Duplicate Rate
```bash
samtools flagstat marked.bam
# Look for "duplicates" line
```

### Count Duplicates
```bash
# Count reads with duplicate flag
samtools view -c -f 1024 marked.bam
```

### Percentage Duplicates
```bash
total=$(samtools view -c marked.bam)
dups=$(samtools view -c -f 1024 marked.bam)
echo "scale=2; $dups * 100 / $total" | bc
```

## pysam Python Alternative

### Full Pipeline
```python
import pysam

# Sort by name
pysam.sort('-n', '-o', 'namesort.bam', 'input.bam')

# Fixmate
pysam.fixmate('-m', 'namesort.bam', 'fixmate.bam')

# Sort by coordinate
pysam.sort('-o', 'coordsort.bam', 'fixmate.bam')

# Mark duplicates
pysam.markdup('coordsort.bam', 'marked.bam')

# Index
pysam.index('marked.bam')
```

### Check Duplicate Flag
```python
import pysam

with pysam.AlignmentFile('marked.bam', 'rb') as bam:
    total = 0
    duplicates = 0
    for read in bam:
        total += 1
        if read.is_duplicate:
            duplicates += 1

    print(f'Total: {total}')
    print(f'Duplicates: {duplicates}')
    print(f'Rate: {duplicates/total*100:.2f}%')
```

### Filter Out Duplicates
```python
import pysam

with pysam.AlignmentFile('marked.bam', 'rb') as infile:
    with pysam.AlignmentFile('nodup.bam', 'wb', header=infile.header) as outfile:
        for read in infile:
            if not read.is_duplicate:
                outfile.write(read)
```

### Production Tools, Not Hand-Rolled

For real BAMs, always use a production marker. A naive Python implementation keyed on (chrom, pos, strand) ignores 5' position correction for soft clips, ignores library/RG, treats optical = PCR, and mis-handles supplementary alignments. The result is silently wrong duplicate marks. Use `samtools markdup`, Picard, or fgbio depending on assay (see decision tables above).

## Alternative: From Aligner

Some aligners can mark duplicates directly during streaming:

### BWA-MEM2 with samblaster
```bash
bwa-mem2 mem ref.fa R1.fq R2.fq | \
    samblaster | \
    samtools sort -o marked.bam
```

### Picard MarkDuplicates
```bash
java -jar picard.jar MarkDuplicates \
    I=input.bam \
    O=marked.bam \
    M=metrics.txt \
    OPTICAL_DUPLICATE_PIXEL_DISTANCE=2500
```

## UMI-Aware Deduplication

For UMI libraries (10x scRNA, ctDNA panels, Twist/IDT/Roche UMI capture), naive markdup destroys information. Use UMI-aware tools:

```bash
# 10x / scRNA -- group by cell barcode + UMI
umi_tools dedup --stdin=cellranger_possorted.bam --stdout=dedup.bam \
    --extract-umi-method=tag --umi-tag=UB --cell-tag=CB \
    --per-cell --method=directional

# Bulk UMI / ctDNA -- consensus calling (best practice for low-VAF detection)
fgbio AnnotateBamWithUmis -i raw.bam -f umi.fastq -o annotated.bam
fgbio GroupReadsByUmi -i annotated.bam -o grouped.bam --strategy=adjacency --edits=1
fgbio CallMolecularConsensusReads -i grouped.bam -o consensus.bam --min-reads=1
# Or for duplex (xGen-Prism, NEBNext duplex):
fgbio CallDuplexConsensusReads -i grouped.bam -o duplex.bam --min-reads 1 1 0
```

`--method=directional` is the default and correct -- do not use `--method=unique`, which treats single-base UMI errors as different molecules. `samtools markdup --barcode-tag RX` (UMI/barcode handling added in samtools 1.16) does exact-match UMI grouping; adequate for IDT xGen Duplex but insufficient for single-UMI applications where 1-edit errors are common.

## Quick Reference

| Task | Command |
|------|---------|
| Full workflow | `sort -n \| fixmate -m \| sort \| markdup` |
| Mark duplicates | `samtools markdup in.bam out.bam` |
| Remove duplicates | `samtools markdup -r in.bam out.bam` |
| Count duplicates | `samtools view -c -f 1024 marked.bam` |
| View non-duplicates | `samtools view -F 1024 marked.bam` |
| Get stats | `samtools markdup -s in.bam out.bam` |

## Duplicate FLAG

| Flag | Value | Meaning |
|------|-------|---------|
| 0x400 | 1024 | PCR or optical duplicate |

### Filter Commands
```bash
# View only duplicates
samtools view -f 1024 marked.bam

# View non-duplicates only
samtools view -F 1024 marked.bam

# Count non-duplicates
samtools view -c -F 1024 marked.bam
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `mate not found` | Input not name-sorted | Run `samtools sort -n` first |
| `no MC tag` | fixmate not run with -m | Re-run fixmate with `-m` flag |
| `not coordinate sorted` | Input to markdup not sorted | Run `samtools sort` after fixmate |

## Lossy Operations

`samtools markdup -r` (remove duplicates) is irreversible -- the records are dropped. Default to marking, not removing; downstream tools can filter on FLAG 1024. Removing pre-emptively destroys data needed for re-running QC, library complexity estimation, or switching dedup strategies.

## Related Skills

- alignment-sorting - Sort by name/coordinate; collate vs sort -n decision
- alignment-filtering - Filter duplicates from output
- alignment-amplicon-clipping - Use ampliconclip instead of markdup for amplicon panels
- bam-statistics - Check duplicate rates with flagstat / mosdepth
- variant-calling/variant-calling - Standard variant calling expects deduped BAMs
- read-qc/quality-reports - Pre-alignment QC including UMI extraction

## Usage Guide

# Duplicate Handling - Usage Guide

## Overview
Mark and remove PCR and optical duplicates from alignment files to prevent bias in downstream variant calling and peak detection.

## Prerequisites
```bash
# samtools
conda install -c bioconda samtools

# pysam
pip install pysam
```

## Quick Start
Tell your AI agent what you want to do:
- "Mark duplicates in my BAM file"
- "Remove PCR duplicates from my alignment"
- "Calculate the duplicate rate for my sample"
- "Run the full duplicate marking workflow"

## Example Prompts

### Marking Duplicates
> "Mark duplicates in sample.bam and keep them flagged"

> "Remove duplicates completely from my BAM file"

> "Mark duplicates and generate statistics"

### Workflow Operations
> "Run the complete fixmate and markdup pipeline"

> "Prepare my BAM for duplicate marking with fixmate"

> "Mark duplicates with optical duplicate detection for NovaSeq data"

### Quality Assessment
> "Calculate the duplicate rate for my sample"

> "Check if my duplicate rate is acceptable for WGS"

> "Compare duplicate rates across my samples"

## What the Agent Will Do

1. Sort the BAM file by read name if not already sorted
2. Add mate information using fixmate with the -m flag
3. Re-sort by coordinate position
4. Mark (or remove) duplicates using markdup
5. Generate duplicate statistics
6. Index the final BAM file
7. Report the duplicate rate and assess quality

## The Standard Workflow

```
Input BAM (any order)
    |
    v
samtools sort -n (name sort)
    |
    v
samtools fixmate -m (add mate info)
    |
    v
samtools sort (coordinate sort)
    |
    v
samtools markdup (mark/remove duplicates)
    |
    v
samtools index (create index)
    |
    v
Final BAM (coordinate sorted, duplicates marked)
```

## Common Commands

### Step-by-Step
```bash
samtools sort -n -@ 4 -o namesort.bam input.bam
samtools fixmate -m -@ 4 namesort.bam fixmate.bam
samtools sort -@ 4 -o coordsort.bam fixmate.bam
samtools markdup -@ 4 coordsort.bam marked.bam
samtools index marked.bam
```

### Pipeline (No Intermediate Files)
```bash
samtools sort -n -@ 4 input.bam | \
    samtools fixmate -m -@ 4 - - | \
    samtools sort -@ 4 - | \
    samtools markdup -@ 4 - marked.bam
samtools index marked.bam
```

### Mark vs Remove
```bash
samtools markdup input.bam marked.bam           # Mark only (FLAG 0x400)
samtools markdup -r input.bam deduped.bam       # Remove duplicates
```

### With Statistics
```bash
samtools markdup -s input.bam marked.bam 2> stats.txt
samtools markdup -f stats.txt input.bam marked.bam
```

### Optical Duplicates (Patterned Flowcells)
```bash
samtools markdup -d 100 input.bam marked.bam   # HiSeq (unpatterned)
samtools markdup -d 2500 input.bam marked.bam  # NovaSeq, NextSeq
# HiSeq: -d 100; NovaSeq/NextSeq patterned: -d 2500. See this reference document for full optical-distance matrix.
```

### Check Duplicate Rate
```bash
samtools flagstat marked.bam | grep duplicates

# Calculate percentage
total=$(samtools view -c -F 256 marked.bam)
dups=$(samtools view -c -f 1024 -F 256 marked.bam)
echo "Duplicate rate: $(echo "scale=2; $dups * 100 / $total" | bc)%"
```

## Python with pysam

### Full Workflow
```python
import pysam
import os

def mark_duplicates(input_bam, output_bam, threads=4):
    temp_ns = 'temp_namesort.bam'
    temp_fm = 'temp_fixmate.bam'
    temp_cs = 'temp_coordsort.bam'

    try:
        pysam.sort('-n', '-@', str(threads), '-o', temp_ns, input_bam)
        pysam.fixmate('-m', '-@', str(threads), temp_ns, temp_fm)
        pysam.sort('-@', str(threads), '-o', temp_cs, temp_fm)
        pysam.markdup('-@', str(threads), temp_cs, output_bam)
        pysam.index(output_bam)
    finally:
        for f in [temp_ns, temp_fm, temp_cs]:
            if os.path.exists(f):
                os.remove(f)
```

### Check Duplicate Rate
```python
import pysam

def duplicate_rate(bam_path):
    with pysam.AlignmentFile(bam_path, 'rb') as bam:
        total, duplicates = 0, 0
        for read in bam:
            if read.is_secondary or read.is_supplementary:
                continue
            total += 1
            if read.is_duplicate:
                duplicates += 1
    return {'total': total, 'duplicates': duplicates, 'rate': duplicates / total * 100 if total > 0 else 0}
```

### Filter Duplicates
```python
import pysam

def remove_duplicates(input_bam, output_bam):
    with pysam.AlignmentFile(input_bam, 'rb') as infile:
        with pysam.AlignmentFile(output_bam, 'wb', header=infile.header) as outfile:
            for read in infile:
                if not read.is_duplicate:
                    outfile.write(read)
```

## Expected Duplicate Rates

See this reference document "When to Mark Duplicates" decision table for assay-specific expected duplicate rates.

High duplicate rates suggest:
- Low library complexity
- Over-amplification during PCR
- Low input DNA quantity

## Troubleshooting

### "mate not found"
Input to fixmate is not name-sorted:
```bash
samtools sort -n -o namesorted.bam input.bam
samtools fixmate -m namesorted.bam fixmate.bam
```

### "no MC tag found"
fixmate was not run with `-m` flag:
```bash
samtools fixmate -m namesorted.bam fixmate.bam  # Include -m
```

### "not coordinate sorted"
Input to markdup is not coordinate-sorted:
```bash
samtools sort -o coordsorted.bam fixmate.bam
samtools markdup coordsorted.bam marked.bam
```

### High Memory Usage
markdup loads read information into memory. Increase parallelization:
```bash
samtools markdup -@ 8 input.bam marked.bam
```

## Tips
- Always use the full workflow: name-sort, fixmate -m, coord-sort, markdup
- Mark duplicates before variant calling to prevent bias
- For RNA-seq, usually do NOT remove duplicates (biological duplicates expected)
- The -m flag in fixmate is essential for markdup to work properly
- Use -d 2500 for patterned flowcells (NovaSeq, NextSeq)
- Keep the marked BAM even if duplicate rate seems high - filtering can be done later
- Use samblaster for inline marking during alignment

## Bundled Files

- `alignment-files--duplicate-handling--examples--markdup_pipeline.sh` — copied from `examples/markdup_pipeline.sh`
