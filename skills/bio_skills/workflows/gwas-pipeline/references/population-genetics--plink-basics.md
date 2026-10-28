# bio-population-genetics-plink-basics

> Bundled component reference for `population-genetics/plink-basics` (original source: `skills/bio_skills/population-genetics/plink-basics`).

Manages PLINK genotype filesets - format conversion (VCF, BED/BIM/FAM, PED/MAP, pgen/pvar/psam) and sample/variant QC (missingness, MAF, HWE, sex check, heterozygosity, KING relatedness) with PLINK 1.9 and 2.0. PLINK rewrites allele bookkeeping: PLINK 1.x A1 defaults to the minor allele and is recomputed every load, silently flipping effect-allele meaning unless --keep-allele-order, while PLINK 2.0 tracks explicit REF/ALT. QC order matters (variant before sample missingness), HWE is controls-only in 1.9 but not 2.0, add midp, and differential case/control missingness injects false hits. Use when converting between PLINK formats or running genotype QC before association, structure, or LD analysis. For LD pruning/clumping see linkage-disequilibrium; for GWAS see association-testing; VCF input from variant-calling/vcf-basics.

## Instructions

## Version Compatibility

Reference examples tested with: PLINK 1.9 (1.90b7+), PLINK 2.0 (alpha 6+), pandas 2.2+.

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

Version traps that change results, not just syntax: PLINK 2.0 `--freq` reports ALT/nonmajor allele frequency, PLINK 1.9 `--freq` reports MAF. PLINK 2.0 has no `--recode` (use `--export`) and cannot read `.ped/.map` (convert with 1.9 first). PLINK 2.0 `--hwe` is NOT controls-only by default; PLINK 1.9 is. Missing-rate outputs are `.smiss/.vmiss` (2.0) vs `.imiss/.lmiss` (1.9). PLINK 2.0 dropped `--genome`; use `--make-king` for relatedness. The single source of truth for versions is this block, not headings.

# PLINK Basics

**"Convert my VCF to PLINK and run QC"** -> Project a VCF into a PLINK fileset and apply sample/variant quality filters, holding the allele coding and filter order fixed so downstream effect estimates stay meaningful.
- CLI: `plink2 --vcf in.vcf.gz --make-pgen` (keeps REF/ALT and dosage) or `--make-bed` (biallelic hard calls, A1/A2)
- CLI: `plink2 --geno 0.02` then `plink2 --mind 0.02 --maf 0.01 --hwe 1e-6 midp` (ordered QC)

Scope: PLINK file formats, conversion, and sample/variant QC (missingness, MAF, HWE, sex check, heterozygosity, KING relatedness, merging). LD pruning/clumping (`--indep-pairwise`, `--clump`) route to linkage-disequilibrium; PCA/ADMIXTURE to population-structure; `--glm` GWAS to association-testing; VCF generation to variant-calling/vcf-basics.

## The Single Most Important Insight -- PLINK is a stateful rewriter of allele bookkeeping, not a calculator

1. The most expensive error in the field is trusting that the allele an effect estimate is "for" is the allele assumed. PLINK 1.x has no reference allele: it tracks A1 (the counted/effect allele) and A2, and **A1 defaults to the minor allele, recomputed from the data at load time**. The same SNP flips A1 between two cohorts when the minor allele differs by a few percent, and every `--make-bed` re-derives A2 as the major allele unless `--keep-allele-order` is passed. Betas, odds ratios, and PRS weights are all relative to A1 and become meaningless across cohorts that were not harmonized.
2. PLINK 2.0 fixed the **design** by tracking explicit REF/ALT in `.pvar` (REF is the genuine reference base; the counted allele for `--glm` is set independently), but exporting back to `.bed` collapses into the A1/A2 world and re-inherits the trap.
3. Pinning alleles to a fixed reference (`--ref-allele`/`--a1-allele` from a file, `--ref-from-fa`, or staying in `.pgen`) plus `--keep-allele-order` on any `.bed` export is the line between reproducible and quietly-wrong analysis.
4. Two QC choices silently corrupt association before any test is run: filter **order** (sample-vs-variant missingness) and the **case/control missingness confounder**. Both are covered below.

## Tool Taxonomy -- PLINK 1.9 vs PLINK 2.0

| Axis | PLINK 1.9 (`plink`) | PLINK 2.0 (`plink2`) |
|------|---------------------|----------------------|
| Status / model | Stable, feature-frozen; hard calls only; A1/A2 | Active; hard calls and dosages; explicit REF/ALT, multiallelic-aware |
| Native format | `.bed/.bim/.fam` | `.pgen/.pvar/.psam` |
| Allele bookkeeping | A1 = minor by default (the trap) | REF/ALT tracked; counted allele explicit |
| PED/MAP (`--file`) | Yes | No (convert via 1.9) |
| IBD `--genome` / `--cluster` | Yes | No (use 1.9 or KING) |
| KING-robust relatedness | No | `--make-king`, `--king-cutoff` |
| Multi-fileset merge | `--bmerge` / `--merge-list` (battle-tested) | `--pmerge` / `--pmerge-list` (newer) |
| HWE default | controls-only | NOT controls-only |
| `--freq` default | MAF | ALT/nonmajor frequency |
| Missing-rate output | `.imiss` / `.lmiss` | `.smiss` / `.vmiss` |
| Speed/memory at biobank N | baseline | substantially faster, lower memory |

## Decision Tree by Scenario

| Scenario | Use | Why |
|----------|-----|-----|
| Imputed data with dosage uncertainty | plink2 `.pgen` | 1.9 hard-calls and discards dosage |
| Relatedness in a structured/multi-ancestry sample | plink2 `--make-king` | PI_HAT (`--genome`) is biased under structure; KING gives negative kinship for cross-ancestry unrelateds |
| Classic multi-dataset merge | plink1.9 `--bmerge`/`--merge-list` | most documented and predictable path |
| IBD `--genome` / IBS `--cluster` | plink1.9 | plink2 dropped these |
| Reading PED/MAP or Affymetrix-era text | plink1.9 `--file` | plink2 cannot read them |
| Big modern QC/association/PCA inputs | plink2, export `.bed` last | speed plus correct allele handling; minimize time in A1/A2 land |
| Default working format | stay in `.pgen` through QC | keeps REF/ALT honest; export `.bed` only when a tool demands it (then `--keep-allele-order`) |

## File Formats

| Binary (1.9) | Contents | PLINK 2.0 | Contents |
|------|----------|-----------|----------|
| `.bed` | binary hard-call genotypes (biallelic only) | `.pgen` | genotypes + dosages, multiallelic-aware |
| `.bim` | variant info (chr, ID, cM, pos, **A1, A2**) | `.pvar` | variant info with genuine **REF/ALT** |
| `.fam` | sample info (FID, IID, father, mother, sex, pheno) | `.psam` | sample info |

Text `.ped/.map` (PLINK 1.9 `--file`) is legacy; convert to binary once and work from there.

## Format Conversion

```bash
# VCF -> PLINK. --make-pgen preserves REF/ALT and dosage; --make-bed collapses to A1/A2 hard calls.
plink2 --vcf in.vcf.gz --make-pgen --out data            # preferred working format
plink2 --vcf in.vcf.gz --double-id --make-bed --out data # biallelic hard calls; --double-id copies the VCF sample name into both FID and IID

# Keep the reference allele honest when leaving pgen for bed (otherwise A2 is re-set to major):
plink2 --pfile data --ref-from-fa --fa GRCh38.fa --make-bed --keep-allele-order --out data_bed

# PLINK -> VCF. plink2 uses --export (no --recode); add bgz to compress.
plink2 --bfile data --export vcf bgz --out out
plink  --bfile data --recode vcf --out out               # PLINK 1.9 idiom

# PED/MAP must be read by PLINK 1.9; plink2 cannot.
plink --file textdata --make-bed --out data
```

Multiallelic sites cannot live in `.bed` (biallelic by construction). Split first with `bcftools norm -m-` or accept plink2's split, and track which records changed. Strand-flip logic cannot operate on indels; `--snps-only just-acgt` removes them when needed.

## Quality Control Filtering

```bash
# Variant missingness FIRST, in its own run, so a sample is not dropped for missingness driven by variants slated for removal.
plink2 --pfile data --geno 0.02 --make-pgen --out step1     # default --geno is 0.1; GWAS QC tightens to 0.02-0.05

# THEN sample missingness, MAF, and HWE on the surviving variants.
plink2 --pfile step1 --mind 0.02 --maf 0.01 --hwe 1e-6 midp --make-pgen --out step2
```

HWE caveats that change which variants survive:
- `midp` is not optional. The plain exact test is discrete and conservative for low-count genotypes, biasing toward retaining variants with missing data; mid-p brings rejection to nominal (Graffelman 2013).
- **Apply HWE to controls only.** A true risk variant depletes heterozygotes in cases and would fail a case-inclusive HWE test and be wrongly removed. PLINK 1.9 does this automatically; override with the `include-nonctrl` modifier. **plink2 does NOT** - replicate the behavior with `--keep-if "PHENO1 == control"` before `--hwe`, or the rewrite over-filters real associations.
- In a structured sample the Wahlund effect reduces heterozygosity, so a two-sided HWE filter drops real variants; many genotyping artifacts (contamination, paralog mismapping) instead inflate heterozygosity, so under structure a one-sided excess-het filter (plink2 `keep-fewhet`) avoids dropping Wahlund-deficient real variants.

```bash
# Differential missingness: a top source of false GWAS hits. A variant genotyped less well in cases than controls
# correlates missingness with phenotype; a flat --geno keeps it and injects association.
plink2 --bfile data --pheno pheno.txt --test-missing --out diffmiss   # drop variants with case/control missingness skew
```

## Sample QC

```bash
# Sex check. Split the pseudoautosomal region FIRST or male PAR heterozygosity reads as a sex error.
plink2 --bfile data --split-par hg38 --check-sex --out sexcheck   # PLINK 1.9 uses --split-x hg38
# Default calls: F < 0.2 -> female, F > 0.8 -> male, between -> PROBLEM. These ~2007 defaults are often wrong
# for modern arrays; plot the F histogram and re-pick thresholds at the gap between the two clumps.

# Heterozygosity outliers, on LD-pruned MAF-filtered SNPs only (raw data is dominated by a few regions).
plink2 --bfile data_pruned --het --out het   # flag |F - cohort_mean| > 3 SD: excess het = contamination, deficit = inbreeding/dup

# Relatedness. KING-robust is structure-robust; PI_HAT (--genome) is not.
plink2 --bfile data --make-king-table --out king
plink2 --bfile data --king-cutoff 0.0884 --out unrelated   # prune to no-closer-than 2nd-degree (dup 0.354, 1st 0.177, 2nd 0.0884)
```

`--check-sex` and heterozygosity outliers usually signal a sample swap or contamination, not biology - investigate the sample before dropping it. KING uses autosomes only; the same negative bias that makes cross-ancestry unrelated pairs read below zero also pulls true cross-ancestry relatives toward zero, so KING UNDER-detects relatives in admixed or multi-ancestry cohorts (use PC-Relate / PC-AiR there, out of scope here).

## Merging Datasets

```bash
plink --bfile data1 --bmerge data2 --make-bed --out merged
# Aborts with a "3+ alleles" error when the same SNP is on opposite strands (A/G vs T/C). Flip the offenders, then retry:
plink --bfile data2 --flip merged-merge.missnp --make-bed --out data2_flipped
```

`--flip` swaps A<->T and C<->G only and **cannot disambiguate palindromic A/T and C/G SNPs** (identical on both strands) - resolve those by allele frequency or drop them. Harmonize variant IDs to `chr:pos:ref:alt` (`--set-all-var-ids @:#:\$r:\$a`) before merging so the key is positional and allele-aware, not rsID-collision-prone. Build mismatch (hg19 vs hg38) requires liftover first, which can itself flip strand in inverted regions.

## Per-Operation Failure Modes

### A1/A2 effect-allele flip
**Trigger:** `--make-bed` without `--keep-allele-order`, or merging two cohorts. **Mechanism:** A1 is re-derived as the minor allele from whatever data is present. **Symptom:** betas/ORs/PRS weights point at the wrong allele; meta-analysis cancels true signal. **Fix:** `--keep-allele-order` on every `.bed` export and pin alleles from a fixed reference (`--ref-from-fa` / `--a1-allele`).

### Wrong QC order
**Trigger:** `--geno` and `--mind` in one command. **Mechanism:** plink applies `--mind` (sample) before `--geno` (variant) in a single run; published QC wants variants dropped first. **Symptom:** good samples removed for missingness caused by variants that were about to be filtered. **Fix:** run `--geno` and `--mind` in separate invocations, variant filter first.

### Differential missingness
**Trigger:** case/control cohorts genotyped in separate batches. **Mechanism:** missingness correlates with phenotype; a flat `--geno` retains the variant. **Symptom:** false genome-wide hits at batch-skewed sites. **Fix:** `--test-missing` and drop variants with case/control missingness skew, not just a global `--geno`.

### Phenotype encoding inversion
**Trigger:** loading a 0/1 case/control file without `--1`. **Mechanism:** PLINK reads `1`=control, `2`=case, `0`/`-9`=missing by default; a 0/1 file makes every case read as control and every control as missing. **Symptom:** silent, total phenotype corruption; null or inverted GWAS. **Fix:** `--1` for 0/1 coding; any value outside {-9,0,1,2} is treated as quantitative.

### PAR not split before sex/X analysis
**Trigger:** `--check-sex` or X-specific work without `--split-par`/`--split-x`. **Mechanism:** male PAR is diploid and heterozygous; uncoded it looks like X het. **Symptom:** males mis-called female; spurious sex PROBLEMs. **Fix:** `--split-par <build>` with the correct genome build (hg19 vs hg38 boundaries differ).

## Quantitative Thresholds

| Operation | Flag | Typical value | Rationale |
|-----------|------|---------------|-----------|
| Variant missingness | `--geno` | 0.02 (PCA/structure), 0.05 (standard) | default 0.1; >2-5% missing flags batch artifacts |
| Sample missingness | `--mind` | 0.02-0.05 | default 0.1; apply AFTER `--geno` |
| MAF | `--maf` | 0.01 (common-variant GWAS), 0.05 (PCA), down to 0.001 at large N | below ~0.01 power and HWE/sex-check stability collapse |
| HWE | `--hwe ... midp` | 1e-6 controls-only | loose vs association: screens artifacts, not biology |
| Sex F | `--check-sex` | female <0.2, male >0.8 (default) | re-pick from the F histogram gap |
| Heterozygosity | `--het` | \|F - mean\| > 3 SD | excess het = contamination, deficit = inbreeding/dup; on LD-pruned SNPs |
| Relatedness (KING) | `--king-cutoff` | 0.0884 (2nd-deg+), 0.177 (1st), 0.354 (dup/MZ cutoff; a true MZ/dup pair sits at ~0.5) | KING boundaries, Manichaikul 2010 |

Thresholds are conventions, not laws - inspect the distributions and verify current best practice before applying numbers blindly.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| `--hwe-all` "unrecognized flag" | flag does not exist | controls-only override is `include-nonctrl` (1.9); plink2 needs `--keep-if "PHENO1 == control"` |
| HWE over-filters real associations | assuming plink2 `--hwe` is controls-only | it is not; gate to controls first; always add `midp` |
| ALT_FREQ read as MAF | plink2 `--freq` reports ALT frequency | inspect columns; PLINK 1.9 `--freq` reports MAF |
| Script reads empty missingness file | wrong suffix | 2.0 `.smiss/.vmiss`, 1.9 `.imiss/.lmiss` |
| `--keep-fam sample_id` keeps nothing | `--keep-fam` takes a FILE of FIDs | use `--keep` with a FID IID file |
| Frequencies use a subset in family data | MAF/HWE/`--freq` are founders-only | add `--nonfounders` if intended |
| Duplicate variant IDs break `--extract`/merge | duplicate IDs | `--rm-dup force-first` or set `chr:pos:ref:alt` IDs |

## References

1. Purcell S, et al. PLINK: a tool set for whole-genome association and population-based linkage analyses. American Journal of Human Genetics 2007; 81(3):559-575. DOI:10.1086/519795.
2. Chang CC, Chow CC, Tellier LCAM, Vattikuti S, Purcell SM, Lee JJ. Second-generation PLINK: rising to the challenge of larger and richer datasets. GigaScience 2015; 4:7. DOI:10.1186/s13742-015-0047-8.
3. Manichaikul A, Mychaleckyj JC, Rich SS, Daly K, Sale M, Chen W-M. Robust relationship inference in genome-wide association studies. Bioinformatics 2010; 26(22):2867-2873. DOI:10.1093/bioinformatics/btq559.
4. Wigginton JE, Cutler DJ, Abecasis GR. A note on exact tests of Hardy-Weinberg equilibrium. American Journal of Human Genetics 2005; 76(5):887-893. DOI:10.1086/429864.
5. Graffelman J, Moreno V. The mid p-value in exact tests for Hardy-Weinberg equilibrium. Statistical Applications in Genetics and Molecular Biology 2013; 12(4):433-448. DOI:10.1515/sagmb-2012-0039.

## Related Skills

- linkage-disequilibrium - LD pruning and clumping on QC'd genotypes
- population-structure - PCA and ADMIXTURE after QC and relatedness pruning
- association-testing - GWAS with `--glm` on the filtered fileset
- variant-calling/vcf-basics - VCF generation and manipulation before conversion
- phasing-imputation/genotype-imputation - imputed dosages that enter as `.pgen`

## Usage Guide

# PLINK Basics - Usage Guide

## Overview

PLINK is the workhorse for genotype data management and quality control, but it is a stateful rewriter of allele bookkeeping rather than a calculator: PLINK 1.x re-derives the A1 (effect) allele as the minor allele on every load, so effect estimates and PRS weights silently lose their allele anchor unless the alleles are pinned, while PLINK 2.0 tracks genuine REF/ALT. The QC decisions that matter most are not the thresholds but the order (variant missingness before sample missingness), the controls-only HWE convention (automatic in 1.9, manual in 2.0), and the case/control differential-missingness confounder that injects false association.

## Prerequisites

- PLINK 1.9 and PLINK 2.0 installed: `conda install -c bioconda plink plink2`
- Input genotypes as VCF/BCF, BED/BIM/FAM, PED/MAP, or pgen/pvar/psam
- A genome build (hg19 vs hg38) known for the data - PAR boundaries and liftover depend on it
- Conceptual prerequisites and big notes:
  - A1/A2 (1.x) is the counted/effect-allele pair and carries no reference or strand meaning; REF/ALT (2.0) is genuine. Harmonize alleles to a fixed reference before combining cohorts.
  - Run `--geno` (variant) and `--mind` (sample) in separate invocations, variant first, to control the implicit order.
  - HWE filtering is controls-only and should use `midp`; in plink2 the controls-only behavior must be added explicitly.
  - Relatedness in a structured sample needs KING (`--make-king`), not PI_HAT (`--genome`).
  - Split the pseudoautosomal region (`--split-par`) before any sex check or X-specific analysis.

## Quick Start

Tell your AI agent what you want to do:
- "Convert this VCF to a PLINK fileset, keeping REF/ALT honest"
- "Run standard GWAS QC on my genotypes in the correct order"
- "Apply controls-only HWE filtering with mid-p"
- "Find related individuals with KING and prune to unrelated"
- "Check reported sex against X heterozygosity after splitting PAR"
- "Test for differential missingness between cases and controls"
- "Merge two genotype datasets and resolve strand flips"

## Example Prompts

### Conversion
> "Convert imputed.vcf.gz to a PLINK 2.0 pgen fileset preserving dosages, then export a biallelic BED with the reference allele pinned from the GRCh38 FASTA."

### Quality control
> "Run QC on cohort.bed: variant missingness at 0.02, then sample missingness at 0.02, MAF 0.01, and controls-only HWE at 1e-6 with mid-p."

### Sample-level QC
> "Compute KING kinship and remove one of each pair closer than second-degree, and flag heterozygosity outliers beyond 3 SD on LD-pruned SNPs."

### Confounder checks
> "Run a differential-missingness test between my cases and controls and give me the list of variants to drop before GWAS."

## What the Agent Will Do

1. Identify the input format and target, and choose PLINK 1.9 vs 2.0 from the operation (PED/MAP and `--genome` force 1.9; dosages and KING favor 2.0).
2. Convert format, preserving REF/ALT where possible and applying `--keep-allele-order` on any BED export.
3. Apply QC in the order that avoids dropping good samples: variant missingness, then sample missingness, MAF, and controls-only HWE with mid-p.
4. Run sample-level QC: sex check after PAR split, heterozygosity outliers on LD-pruned SNPs, and KING relatedness pruning.
5. Check the differential-missingness confounder before any association.
6. Report which samples and variants were removed at each step and why, so the filtering is auditable.

## Tips

- Stay in `.pgen` through QC if every downstream tool supports it; export `.bed` only as a last step and always with `--keep-allele-order`.
- The thresholds in the skill are starting conventions. Plot missingness, MAF, het-F, and KING distributions and pick cutoffs at the natural gaps.
- Sex-check and heterozygosity failures usually mean a sample swap or contamination - investigate the sample rather than silently dropping it.
- Palindromic A/T and C/G SNPs cannot be strand-resolved by `--flip`; resolve by allele frequency or drop them before merging cohorts.
- After merging, re-apply allele-order discipline - a merge can re-derive A1/A2.

## Related Skills

- linkage-disequilibrium - LD pruning and clumping on QC'd genotypes
- population-structure - PCA and ADMIXTURE after QC and relatedness pruning
- association-testing - GWAS with `--glm` on the filtered fileset
- variant-calling/vcf-basics - VCF generation and manipulation before conversion
- phasing-imputation/genotype-imputation - imputed dosages that enter as `.pgen`

## Bundled Files

- `population-genetics--plink-basics--examples--qc_pipeline.sh` — copied from `examples/qc_pipeline.sh`
