# bio-small-rna-seq-mirge3-analysis

> Bundled component reference for `small-rna-seq/mirge3-analysis` (original source: `skills/bio_skills/small-rna-seq/mirge3-analysis`).

Quantifies known miRNAs, isomiRs, tRFs, and A-to-I editing fast with miRge3.0 by aligning collapsed reads to curated miRBase or MirGeneDB libraries. Use when choosing miRBase versus MirGeneDB as the reference; deciding whether to collapse isomiRs to the parent miRNA or keep 5'-isomiRs separate (they shift the seed and retarget); confirming the organism is among the six supported species; or remembering that RPM output is for display only and raw counts go to DESeq2/edgeR.

## Instructions

## Version Compatibility

Reference examples tested with: miRge3.0 0.1.4+, numpy 1.26+, pandas 2.2+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `miRge3.0 annotate --help` to confirm flag names (they have drifted across versions)
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# miRge3 Analysis

**"Quantify my miRNAs and isomiRs fast"** -> Align collapsed reads to a hierarchy of curated small-RNA libraries and tabulate per-miRNA counts, isomiR variants, tRFs, and A-to-I editing.
- CLI: `miRge3.0 annotate -s sample.fastq.gz -lib LIBS -on human -db miRBase -a illumina -gff -ai -cpu 8 -o out/`

## The governing principle: miRge3 quantifies what is already known, fast, and isomiRs are biology

miRge3.0 does not do genome-wide de novo discovery as its main job; it Bowtie-aligns collapsed reads against small curated libraries (mature miRBase or MirGeneDB, hairpin, tRNA, rRNA, snoRNA, mRNA, spike-ins) hierarchically and assigns each read to the first matching class. That is why it is fast, and why it is the default for a routine differential-expression study on a supported species - and why it cannot help on an unsupported organism (it ships pre-built libraries for only six species: human, mouse, rat, zebrafish, nematode, fruitfly). For serious NOVEL discovery prefer miRDeep2; miRge3's optional `-nmir` SVM module is a convenience, not its strength.

Two judgments carry the analysis. First, isomiRs are real biology, not noise: a 5' isomiR shifts the seed (positions 2-7) and therefore the target set, so collapsing all isomiRs to the canonical miRNA can hide function - keep 5' isomiRs separate when isomiR identity is the question, and collapse to the parent only for a standard "which miRNAs changed" analysis. But the precision floor cuts the other way: low-count 3' and internal isomiRs are frequently sequencing/ligation artifacts (per-base error ~0.1-1% plus ligation bias), so filter them aggressively and demand replicate or UMI support, and trust 5' isomiRs more. A germline seed SNP (a polymiR) masquerades as an isomiR or edit; with genotypes available, fold them into the reference (e.g. OptimiR) rather than calling them isomiRs. Second, miRge3 emits both raw counts and RPM, but RPM is for display and cross-sample viewing only; differential testing takes RAW counts into DESeq2/edgeR, which model the count distribution themselves.

## Decision: miRBase vs MirGeneDB reference (`-db`)

| Reference | Size | Character | Choose when |
|-----------|------|-----------|-------------|
| miRBase (v22) | large (~1900 human miRNAs) | permissive; includes many dubious entries (mis-annotated tRFs/fragments) | maximizing recall / comparability with legacy studies |
| MirGeneDB | small (~550 human genes) | conservatively curated; every entry passes the biogenesis signature | conservative, high-confidence claims; cleaner DE feature set |

The reference choice changes results: counting against miRBase yields more "miRNA" rows, some of which are not bona fide miRNAs; against MirGeneDB the rows are fewer and defensible. miRge3 can emit both side by side - report which one a result came from, and pin the version.

## Library installation (no built-in download command)

```bash
# miRge3.0 has NO '--download-library' subcommand. Fetch the pre-built libraries from
# SourceForge and extract them, then point -lib at the extracted directory.
wget https://sourceforge.net/projects/mirge3/files/miRge3_Lib/human.tar.gz
tar -xzf human.tar.gz          # creates a 'human' library tree
# For an unsupported organism, build a custom library with the separate miRge3_build tool.
```

## Quantify known miRNAs (+ isomiRs, A-to-I)

**Goal:** Produce a per-miRNA count matrix with isomiR and editing detail for one or more samples.

**Approach:** Run `miRge3.0 annotate` with the curated library, organism, database, and adapter, switching on mirGFF3 isomiR output and A-to-I detection.

```bash
miRge3.0 annotate \
    -s sample1.fastq.gz,sample2.fastq.gz \
    -lib /path/to/miRge3_Lib \
    -on human \
    -db miRBase \
    -a illumina \
    -gff \
    -ai \
    -cpu 8 \
    -o output_dir

# -s: comma-separated FASTQs (raw or already adapter-known)
# -on: organism (human|mouse|rat|zebrafish|nematode|fruitfly)
# -db: miRBase or MirGeneDB
# -a: adapter as a name ('illumina') OR a raw sequence (e.g. TGGAATTCTCGGGTGCCAAGG)
# -gff: emit isomiR results in mirGFF3 (the community-standard isomiR format)
# -ai: A-to-I editing. A seed A->I edit RETARGETS the miRNA (inosine reads as G), and
#      mismatch-permissive alignment silently merges edited reads into the canonical
#      count - keep -ai on and treat seed edits as distinct species, not noise.
# -cpu: threads
```

## UMI and novel-miRNA options

```bash
# QIAseq UMI library: -qumi removes Qiagen PCR duplicates; -umi gives the 5',3' trim lengths
miRge3.0 annotate -s qiaseq.fastq.gz -lib LIBS -on human -db miRBase \
    -a AACTGTAGGCACCATCAAT -umi 0,12 -qumi -o out_umi

# Optional novel-miRNA prediction (SVM); needs the genome; prefer miRDeep2 for real discovery
miRge3.0 annotate -s sample.fastq.gz -lib LIBS -on human -db miRBase -a illumina -nmir -o out_novel
```

## Output files

| File | Description |
|------|-------------|
| miR.Counts.csv | Raw read counts per miRNA (this feeds DESeq2/edgeR) |
| miR.RPM.csv | RPM-normalized counts (display only, NOT for DE testing) |
| *.gff3 | isomiR variants in mirGFF3 (with `-gff`) |
| annotation.report.html / .csv | RNA-class composition and QC report |
| a2i / editing report | A-to-I editing sites and frequencies (with `-ai`) |

## Run from Python via subprocess

**Goal:** Orchestrate miRge3 from a Python pipeline and load its outputs.

**Approach:** miRge3.0 is a command-line tool with no documented Python API, so invoke it with subprocess, then read the CSV outputs with pandas.

```python
import subprocess

def run_mirge3(samples, lib_path, out_dir, organism='human', db='miRBase', adapter='illumina', threads=8):
    cmd = ['miRge3.0', 'annotate',
           '-s', ','.join(samples),
           '-lib', lib_path,
           '-on', organism,
           '-db', db,
           '-a', adapter,
           '-gff', '-ai',
           '-cpu', str(threads),
           '-o', out_dir]
    subprocess.run(cmd, check=True)
```

## Load and filter counts

**Goal:** Read the miRge3 count matrix and remove near-zero noise before downstream analysis.

**Approach:** Load `miR.Counts.csv`, then filter to miRNAs with a minimum total count (most miRBase entries are near-zero noise).

```python
import pandas as pd

def load_mirge3_counts(output_dir):
    return pd.read_csv(f'{output_dir}/miR.Counts.csv', index_col=0)

def filter_low_counts(counts, min_total=10):
    # Lower than an mRNA threshold because miRNA libraries have fewer total counts;
    # hand the SURVIVING RAW counts (not RPM) to DESeq2/edgeR for testing.
    return counts[counts.sum(axis=1) >= min_total]
```

## Aggregate isomiRs deliberately

**Goal:** Decide whether to collapse isomiRs to the parent miRNA or keep seed-shifting 5' variants separate.

**Approach:** Parse the mirGFF3 isomiR table, classify each variant by 5' vs 3' change, and aggregate to the parent only for variants that preserve the seed.

```python
def summarize_isomirs(isomir_counts):
    # 5' isomiRs shift the seed and retarget -> keep separate when isomiR identity is
    # the biology; 3' isomiRs mostly tune stability -> safe to collapse to the parent.
    # KEEP the -5p/-3p arm in the parent key: the two arms have different seeds and
    # targets and must never be merged (the dominant arm also switches across tissues).
    # .values assigns positionally - index.str.extract returns a fresh RangeIndex that
    # would otherwise misalign to all-NaN against the string index.
    isomir_counts['miRNA'] = isomir_counts.index.str.extract(r'(hsa-\w+-\d+[a-z]*(?:-[35]p)?)')[0].values
    summary = isomir_counts.groupby('miRNA').agg(
        total_reads=('count', 'sum'),
        n_isomirs=('count', 'count'),
        dominant_isomir=('count', lambda x: x.idxmax()))
    return summary
```

## Common Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `unrecognized arguments: --isomir` | Flag does not exist | isomiR counts are produced by default; use `-gff` for mirGFF3 output |
| `unrecognized arguments: --download-library` | No such subcommand | Download libraries from SourceForge and `tar -xzf`; point `-lib` at the tree |
| `ModuleNotFoundError: mirge3.annotate` | No documented Python API | Call the CLI with `subprocess.run([...])` |
| Empty or tiny count matrix | Wrong `-on`, wrong `-db` case, or wrong adapter | Confirm a supported species; `-db miRBase`/`MirGeneDB`; check the adapter name/sequence |
| Organism not supported | Only six species ship libraries | Build a custom library with miRge3_build, or use miRDeep2/sRNAbench |
| Inflated DE significance on tiny miRNAs | RPM fed to the DE test | Feed RAW `miR.Counts.csv`, not `miR.RPM.csv`, to DESeq2/edgeR |

## Related Skills

- smrna-preprocessing - Adapter and UMI handling; miRge3 can also trim internally
- mirdeep2-analysis - Use when de novo novel-miRNA discovery is the goal
- differential-mirna - Differential expression from the raw count matrix
- trf-pirna-profiling - Deeper tRF/piRNA analysis beyond miRge3's tRF module

## References

- Patil AH, Halushka MK. 2021. miRge3.0: a comprehensive microRNA and tRF sequencing analysis pipeline. *NAR Genom Bioinform* 3:lqab068. doi:10.1093/nargab/lqab068
- Desvignes T, Loher P, Eilbeck K, et al. 2020. Unification of miRNA and isomiR research: the mirGFF3 format and the mirtop API. *Bioinformatics* 36:698-703. doi:10.1093/bioinformatics/btz675
- Kozomara A, Birgaoanu M, Griffiths-Jones S. 2019. miRBase: from microRNA sequences to function. *Nucleic Acids Res* 47:D155-D162. doi:10.1093/nar/gky1141
- Fromm B, Domanska D, Høye E, et al. 2020. MirGeneDB 2.0: the metazoan microRNA complement. *Nucleic Acids Res* 48:D1172-D1180. doi:10.1093/nar/gkz885
- Tan GC, Chan E, Molnar A, et al. 2014. 5' isomiR variation is of functional and evolutionary importance. *Nucleic Acids Res* 42:9424-9435. doi:10.1093/nar/gku656

## Usage Guide

# miRge3 Analysis - Usage Guide

## Overview

Quantify known miRNAs, isomiRs, tRFs, and A-to-I editing quickly with miRge3.0, which Bowtie-aligns collapsed reads to curated miRBase or MirGeneDB libraries rather than doing genome-wide discovery. This makes it the default tool for a routine differential-expression study on one of the six supported species (human, mouse, rat, zebrafish, nematode, fruitfly), but means it cannot help on an unsupported organism. Two judgments matter: choosing miRBase (large, permissive) versus MirGeneDB (small, curated) as the reference, and deciding whether to collapse isomiRs to the parent miRNA or keep seed-shifting 5' isomiRs separate. RPM output is for display only; raw counts go to DESeq2/edgeR for testing.

## Prerequisites

```bash
pip install mirge3
# bowtie (v1), RNAfold (ViennaRNA), and samtools are runtime dependencies

# Libraries are NOT fetched by miRge3 itself - download and extract them from SourceForge:
wget https://sourceforge.net/projects/mirge3/files/miRge3_Lib/human.tar.gz
tar -xzf human.tar.gz
```

## Quick Start

Tell your AI agent:
- "Quantify human miRNAs with miRge3 using MirGeneDB"
- "Emit isomiR results as mirGFF3 and detect A-to-I editing"
- "My organism is not one of the six supported - what are my options?"
- "Give me raw counts for DESeq2, not RPM"
- "Summarize isomiR diversity but keep 5' isomiRs separate"

## Example Prompts

### Basic Quantification

> "Run miRge3 annotate on my trimmed FASTQs with the human miRBase library"

> "Quantify with MirGeneDB instead of miRBase and tell me how the feature count differs"

> "Build a count matrix across all my samples for differential expression"

### IsomiR and Editing Analysis

> "Emit mirGFF3 isomiR output and classify variants as 5' versus 3'"

> "Should I collapse isomiRs to the parent miRNA for my DE analysis?"

> "Detect A-to-I editing sites and report editing frequencies per miRNA"

### Reference and Species Choices

> "My samples are rat - is rat a supported species and which database should I use?"

> "How do I build a custom library for an unsupported organism?"

## What the Agent Will Do

1. Confirm the organism is among the six supported species and locate the extracted library
2. Choose miRBase or MirGeneDB based on whether recall or curation matters, and pin the version
3. Run `miRge3.0 annotate` with the adapter (name or sequence), `-gff` for isomiR mirGFF3, and `-ai` for A-to-I editing
4. Load the raw `miR.Counts.csv` (not RPM) and filter near-zero miRNAs
5. Aggregate isomiRs deliberately - collapsing 3' variants but keeping 5' seed-shifting variants separate when isomiR identity is the question

## Tips

- miRge3 is faster than miRDeep2 for known-miRNA quantification because it aligns to small curated libraries, not the genome
- There is no `--isomir` flag - isomiR counts are produced by default and `-gff` emits the mirGFF3 standard format
- There is no `--download-library` command - libraries come from SourceForge and are extracted with `tar`
- miRge3.0 has no documented Python API; orchestrate it with `subprocess`, not `from mirge3.annotate import ...`
- Only six species ship libraries - for anything else build a custom library with miRge3_build, or use miRDeep2/sRNAbench
- miRBase (large, permissive) versus MirGeneDB (small, curated) genuinely changes the result; report which one you used
- Feed RAW counts to DESeq2/edgeR; RPM is for display only
- 5' isomiRs shift the seed and retarget the miRNA - do not silently collapse them into the canonical sequence
- Low-count 3'/internal isomiRs are often sequencing/ligation artifacts - filter hard and require replicate or UMI support; trust 5' isomiRs more
- A germline seed SNP (polymiR) looks like an isomiR/edit; fold genotypes into the reference (OptimiR) when available
- A seed A-to-I edit retargets the miRNA; keep A-to-I detection on, or permissive alignment silently merges edited reads into the canonical count
- Report and quantify by arm (-5p/-3p), never sum the two arms - the dominant arm switches across tissue/condition and the arms have different seeds and targets

## Related Skills

- smrna-preprocessing - Adapter and UMI handling
- mirdeep2-analysis - Novel miRNA discovery when needed
- differential-mirna - DE from the raw count matrix
- trf-pirna-profiling - Deeper tRF and piRNA analysis

## Bundled Files

- `small-rna-seq--mirge3-analysis--examples--mirge3_quantify.py` — copied from `examples/mirge3_quantify.py`
