# bio-population-genetics-linkage-disequilibrium

> Bundled component reference for `population-genetics/linkage-disequilibrium` (original source: `skills/bio_skills/population-genetics/linkage-disequilibrium`).

Computes linkage disequilibrium (r2, D', composite Rogers-Huff r2), prunes correlated variants, clumps GWAS summary statistics to lead SNPs, and defines haplotype blocks with PLINK 1.9/2.0 and scikit-allel. r2 and D' answer different questions - r2 (= chi2/N) is the tagging and GWAS-power currency, D' marks observed recombination and is upward-biased for rare variants. PLINK 2.0 has no bare --r2 (split into --r2-phased and --r2-unphased); pruning (--indep-pairwise, genotype-blind) and clumping (--clump, p-value-aware) are distinct operations that are constantly confused. The clumping or fine-mapping LD reference must be ancestry-matched or it fails silently into false credible sets. Use when calculating LD, pruning variants for PCA or structure, clumping GWAS hits, or selecting tag SNPs. For QC see plink-basics; for PCA see population-structure; fine-mapping is causal-genomics/fine-mapping.

## Instructions

## Version Compatibility

Reference examples tested with: PLINK 1.9 (1.90b7+), PLINK 2.0 (alpha 6+), scikit-allel 1.3+, numpy 1.26+.

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

Version traps that change results, not just syntax: PLINK 2.0 has NO bare `--r2` (it was split into `--r2-phased`, the EM haplotype-frequency estimator, and `--r2-unphased`, the composite dosage estimator); PLINK 1.9 still uses bare `--r2`. PLINK 2.0 `--indep-pairwise <window>['kb'] [step] <r2>` requires the step to be 1 when the window is given in kb. `allel.rogers_huff_r` returns a CONDENSED upper-triangle array, not a square matrix - `scipy.spatial.distance.squareform` it before 2D indexing. The single source of truth for versions is this block, not headings.

# Linkage Disequilibrium

**"Measure LD between my variants"** -> Quantify how predictably one variant's alleles co-occur with another's, choosing r2 or D' by the question being asked.
- CLI: `plink2 --r2-unphased` (composite dosage r2, no phasing) or `--r2-phased` (EM haplotype r2)
- Python: `allel.rogers_huff_r(gn) ** 2` (composite r2, scikit-allel)

**"Thin correlated variants before PCA or structure"** -> Remove variants so no remaining pair is in high LD, leaving a near-independent marker set.
- CLI: `plink2 --indep-pairwise 50 5 0.1` (genotype-blind, phenotype-agnostic)
- Python: `allel.locate_unlinked(gn, size=50, step=5, threshold=0.1)` (scikit-allel)

**"Reduce my GWAS hits to one signal per locus"** -> Group correlated associations around the most significant SNP per region.
- CLI: `plink --clump sumstats --clump-p1 5e-8 --clump-r2 0.1 --clump-kb 250`

Scope: LD measures, pruning, clumping, haplotype blocks, and LD decay. QC/conversion route to plink-basics; PCA/ADMIXTURE to population-structure; `--glm` GWAS to association-testing; resolving independent causal variants to causal-genomics/fine-mapping; phased haplotypes to phasing-imputation/haplotype-phasing.

## The Single Most Important Insight -- D' and r2 answer different questions

1. D' measures whether recombination has been observed between two loci (a historical/structural question); r2 measures how well one variant predicts the other (a statistical/predictive question), so they are not interchangeable.
2. r2 owns tagging, imputation, pruning, and GWAS power because r2 = chi2/N exactly (N = number of haplotypes = 2 x sampled individuals, for the 1-df allelic 2x2 table; the composite estimator targets this gametic r2 under random mating): a proxy multiplies the association test's non-centrality by r2, so 1/r2 times the sample size is needed to recover the lost power (Pritchard & Przeworski 2001).
3. D'=1 routinely coexists with r2 ~ 0.05 because allele-frequency asymmetry caps r2: r2/r2max = D'^2 over most of frequency space (VanLiere & Rosenberg 2008), which is exactly why a common array SNP cannot tag a rare causal variant despite "complete LD".
4. Every operation that consumes an LD matrix (clumping, fine-mapping, LD-score regression) silently assumes that matrix matches the study sample's LD; a wrong-ancestry or underpowered reference does not error, it produces confidently wrong output.

## Tool Taxonomy

| Method | Tool / call | Mechanism | When |
|--------|-------------|-----------|------|
| Composite (Rogers-Huff) r2 | `plink2 --r2-unphased`; `allel.rogers_huff_r` | correlation of 0/1/2 dosage vectors, no phasing | robust default when phase or HWE is doubtful |
| EM haplotype r2 | `plink2 --r2-phased`; `vcftools --hap-r2` | infers haplotype frequencies under HWE, then r2 | large HWE-consistent samples, or truly phased input |
| D' | `plink --r2 dprime`; `plink2 --ld <a> <b>` | D normalized by its frequency-constrained max | block boundaries, recombination history (NOT tagging) |
| LD pruning | `plink2 --indep-pairwise`; `allel.locate_unlinked` | genotype-blind windowed r2 thinning | independent marker set for PCA/ADMIXTURE/GRM |
| LD clumping | `plink --clump` | p-value-aware grouping around an index SNP | one lead SNP per associated GWAS locus |
| Haplotype blocks | `plink --blocks no-pheno-req` | Gabriel confidence-interval D' method | block maps, recombination inference |
| LD score regression | `ldsc` (`--l2`, `--h2`, `--rg`) | regress GWAS chi2 on LD score | h2, genetic correlation, confounding from sumstats |

## Decision Tree by Scenario

| Scenario | Use | Why |
|----------|-----|-----|
| Thin variants for PCA/ADMIXTURE/GRM | `--indep-pairwise` after excluding long-range-LD regions | phenotype-blind independence; MHC/inversions must go by coordinate first |
| Reduce GWAS hits to lead SNPs | `--clump` with ancestry-matched LD | p-value-aware; one index SNP per locus |
| Establish independent causal signals | conditional analysis or fine-mapping, NOT tighter clumping | clumping picks the top SNP, not the causal one; over-clumping deletes real secondaries |
| Assess a proxy/tag SNP | r2 (`--r2-unphased`), require r2 >= 0.8 | r2 = fraction of effective N retained at the proxy |
| Define haplotype blocks / recombination | D' (`--blocks`, `--r2 dprime`) | D' marks observed recombination; r2 does not |
| Phase or HWE doubtful, small N, missingness | composite r2 (`--r2-unphased`, Rogers-Huff) | EM can manufacture haplotype-frequency artifacts |
| LD from genotypes in Python at scale | `allel.locate_unlinked` / `allel.rogers_huff_r` | composite estimator, chunkable; no phased-EM in scikit-allel |
| h2 / confounding from summary stats | LD-score regression with ancestry-matched scores | slope = h2, intercept-1 = confounding |

## Pairwise LD and the Phased/Unphased Choice

**Goal:** Compute pairwise r2 (and D' when recombination is the question) without an EM artifact under structure or missingness.

**Approach:** Default to the composite dosage estimator that needs no phasing; reach for EM haplotype r2 only when the sample is large and HWE-consistent, and use D' solely for block/recombination work.

```bash
# Composite dosage r2 (Rogers-Huff): robust default, no HWE assumption.
plink2 --bfile data --r2-unphased --ld-window-kb 1000 --ld-window-r2 0.2 --out ld_unphased

# EM haplotype-frequency r2: only when phase is trustworthy / sample is large and HWE-consistent.
plink2 --bfile data --r2-phased --ld-window-kb 1000 --out ld_phased

# D' for a single pair (recombination / block question), with observed haplotype frequencies.
plink2 --bfile data --ld rs123 rs456 --out pair

# PLINK 1.9 still has the bare --r2; add dprime to also report D'.
plink --bfile data --r2 dprime --ld-window-kb 500 --out ld_dprime
```

```python
import allel
from scipy.spatial.distance import squareform

callset = allel.read_vcf('data.vcf.gz')
gn = allel.GenotypeArray(callset['calldata/GT']).to_n_alt()

# rogers_huff_r returns a CONDENSED upper-triangle vector; square it for r2, squareform for a matrix.
r2_matrix = squareform(allel.rogers_huff_r(gn[:200]) ** 2)
```

## LD Pruning for Structure (genotype-blind)

**Goal:** Produce a near-independent marker set so PCA/ADMIXTURE/GRM are not dominated by a handful of LD blocks.

**Approach:** Exclude long-range-LD regions by coordinate FIRST (their internal r2 is high and real, so a threshold cannot remove them sensibly), then slide an r2 window over the survivors.

```bash
# 1. Drop long-range-LD regions by position (MHC chr6:25-35 Mb, 8p23.1, 17q21.31, LCT/2q21; coordinates are build-specific).
plink2 --bfile data --exclude range longrange_ld.txt --make-bed --out data_noLR

# 2. Windowed r2 prune (50 here is a variant count, so step 5 is fine; step MUST be 1 only with a kb window).
plink2 --bfile data_noLR --indep-pairwise 50 5 0.1 --out prune     # 50-variant window, step 5, r2 0.1
plink2 --bfile data_noLR --extract prune.prune.in --make-bed --out data_pruned
```

```python
import allel

callset = allel.read_vcf('data.vcf.gz')
gn = allel.GenotypeArray(callset['calldata/GT']).to_n_alt()

loc_unlinked = allel.locate_unlinked(gn, size=50, step=5, threshold=0.1)  # boolean keep-mask
gn_pruned = gn.compress(loc_unlinked, axis=0)
```

## Clumping GWAS Summary Statistics (p-value-aware)

**Goal:** Collapse a region of correlated associations to one lead SNP per independent locus.

**Approach:** Index on genome-wide-significant SNPs and absorb nearby LD partners, overriding PLINK's permissive defaults; use an ancestry-matched LD reference, ideally the study sample itself.

```bash
# Defaults (p1=1e-4, p2=1e-2, r2=0.5, kb=250) are neither genome-wide nor strict - set them explicitly.
plink --bfile ld_reference \
    --clump gwas_sumstats.txt \
    --clump-p1 5e-8 --clump-p2 1e-5 --clump-r2 0.1 --clump-kb 250 \
    --out clumped
# clumped.clumped lists one index SNP per locus. This is NOT conditional analysis or fine-mapping.
```

## Haplotype Blocks and LD Decay

**Goal:** Map regions of little observed recombination, or characterize how LD decays with distance.

**Approach:** Use the Gabriel D'-CI block method for boundaries; for decay, bin composite r2 by physical distance after stratifying by population so admixture LD does not flatten the curve.

```bash
plink --bfile data --blocks no-pheno-req --out blocks   # blocks.blocks, blocks.blocks.det (Gabriel CI)
```

```python
import allel, numpy as np

callset = allel.read_vcf('data.vcf.gz')
gn = allel.GenotypeArray(callset['calldata/GT']).to_n_alt()
pos = callset['variants/POS']

n = min(1000, gn.shape[0])
r2, dist = [], []
for i in range(n):
    for j in range(i + 1, min(i + 100, n)):
        r2.append(allel.rogers_huff_r(gn[[i, j]])[0] ** 2)  # condensed length-1 -> index [0]
        dist.append(pos[j] - pos[i])
r2, dist = np.array(r2), np.array(dist)

edges = np.arange(0, 100001, 1000)
decay = [np.mean(r2[(dist >= edges[k]) & (dist < edges[k + 1])]) if ((dist >= edges[k]) & (dist < edges[k + 1])).any() else np.nan for k in range(len(edges) - 1)]
```

## Per-Method Failure Modes

### Long-range-LD regions survive pruning
**Trigger:** `--indep-pairwise` run without excluding MHC/inversions by coordinate. **Mechanism:** their internal r2 is high and genuine, so a window prune keeps a dense cluster. **Symptom:** the top PCs capture the MHC (chr6:25-35Mb) or 17q21.31 inversion, not ancestry. **Fix:** `--exclude range` the long-range-LD list (MHC, 8p23.1, 17q21.31, LCT; Price 2008) before pruning, not a tighter r2.

### D' read as "high LD" for tagging
**Trigger:** selecting tag SNPs or judging proxy adequacy from D'. **Mechanism:** D'=1 only says no recombinant was observed; frequency asymmetry caps r2 far below 1. **Symptom:** a "perfectly linked" common SNP retains almost no association power for a rare causal variant. **Fix:** use r2 for tagging/power and require r2 >= 0.8; reserve D' for blocks.

### D' inflated at rare alleles / small N
**Trigger:** interpreting D' or `--blocks` where minor-allele count is below ~10-20. **Mechanism:** the fourth haplotype is unobserved by chance, pushing the D' MLE to ~1 even for independent loci. **Symptom:** spurious "perfect LD" blocks that vanish with more samples. **Fix:** do not interpret D' at low MAC; report r2, which is noisy but not systematically inflated.

### EM haplotype r2 on structured/missing data
**Trigger:** `--r2-phased` or `--hap-r2` under inbreeding, structure, or high missingness. **Mechanism:** EM converges to biased haplotype frequencies that violate the HWE assumption. **Symptom:** r2 disagrees with the composite estimate and shifts with missingness. **Fix:** use `--r2-unphased` (composite Rogers-Huff) when phase or HWE is doubtful.

### Wrong-ancestry LD reference
**Trigger:** clumping, LD-score regression, or fine-mapping with a panel that does not match the GWAS ancestry. **Mechanism:** the LD matrix consumed differs from the sample's true LD; no error is raised. **Symptom:** mis-grouped clumps, biased heritability, false fine-mapping credible sets with "impossible" configurations. **Fix:** compute LD from the study sample itself, or use an ancestry-matched panel.

### Over-clumping merges independent signals
**Trigger:** treating `--clump` as conditional or fine-mapping analysis. **Mechanism:** clumping keeps the single most significant SNP and discards everything in LD with it. **Symptom:** two truly independent causal variants in modest LD collapse to one locus. **Fix:** use conditional analysis (COJO) or fine-mapping (causal-genomics/fine-mapping); do not just tighten `--clump-r2`.

### LD decay curve flattens at a spurious floor
**Trigger:** plotting LD decay on a pooled multi-population sample. **Mechanism:** admixture and background LD inflate long-range r2 independent of distance. **Symptom:** the decay curve plateaus at a nonzero asymptote instead of decaying toward zero. **Fix:** stratify by population before computing decay (LD ~ 1/(4*Ne*c+1), Hill & Robertson 1968).

## Quantitative Thresholds

| Operation | Flag / value | Typical | Rationale |
|-----------|--------------|---------|-----------|
| Pruning for PCA/ADMIXTURE/GRM | `--indep-pairwise` r2 | 0.1 (range 0.05-0.2) | near-independence so structure is not double-counted; strictness trades marker count for independence |
| Pruning window / step | window / step | 50 var / 5, or 200kb / 1 | window must exceed local LD extent; step is 1 for kb windows in plink2 |
| Pruning for polygenic scores | `--indep-pairwise` r2 | 0.1-0.5 within 250kb-1Mb | retain more signal; tuned by validation |
| Clumping LD threshold | `--clump-r2` | 0.1 (default 0.5 under-clumps) | r2 0.1 within 250kb defines one independent locus; set explicitly |
| Clumping p-values | `--clump-p1` / `--clump-p2` | 5e-8 / 1e-5 (defaults 1e-4/1e-2) | index at genome-wide significance; defaults are neither genome-wide nor strict |
| Tag / proxy adequacy | r2 | >= 0.8 | r2 = chi2/N: retains >= 80% of association power at the proxy (Pritchard & Przeworski 2001) |
| Gabriel "strong LD" block | upper 95% D' CI | > 0.98 (lower > 0.7) | one recombinant makes D'=1 impossible yet the CI can sit just below 1 (Gabriel 2002) |
| MAF floor for stable D' | MAF | >~ 0.05 | D' upward bias and r2 variance both blow up at low MAC |
| LDSC applicability | mean chi2 / N | > ~1.02 / N > ~5000 | below this the slope is too noisy; exclude MHC; munge to HapMap3 SNPs (Bulik-Sullivan 2015) |

Thresholds are conventions, not laws - inspect the LD distributions and verify current best practice before applying numbers blindly.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| `plink2 --r2` "unrecognized flag" | bare `--r2` removed in PLINK 2.0 | choose `--r2-phased` or `--r2-unphased`; PLINK 1.9 keeps `--r2` |
| `--indep-pairwise 50kb 5 0.1` errors | step must be 1 for kb windows | use `--indep-pairwise 50kb 1 0.1` or a variant-count window |
| `rogers_huff_r(gn)[0,1]` index error | function returns a condensed vector | `squareform(rogers_huff_r(gn))` first, or index `[0]` for a single pair |
| Top PCs capture one region | long-range-LD region left in | `--exclude range` MHC/8p23.1/17q21.31/LCT by coordinate before pruning |
| Clumping reports correlated SNPs as separate loci | default `--clump-r2 0.5` too loose | set `--clump-r2 0.1` and `--clump-p1 5e-8` explicitly |
| Independent secondary hit disappears | over-clumping treated as fine-mapping | use conditional analysis / fine-mapping, not a tighter clump |
| False fine-mapping credible sets | wrong-ancestry LD reference | use in-sample or ancestry-matched LD |
| LDSC intercept read as pure stratification | intercept also absorbs sample overlap | use the attenuation ratio (intercept-1)/(mean chi2 - 1) |

## References

1. Lewontin RC. The interaction of selection and linkage. I. General considerations; heterotic models. Genetics 1964; 49(1):49-67.
2. Hill WG, Robertson A. Linkage disequilibrium in finite populations. Theoretical and Applied Genetics 1968; 38(6):226-231. DOI:10.1007/BF01245622.
3. Pritchard JK, Przeworski M. Linkage disequilibrium in humans: models and data. American Journal of Human Genetics 2001; 69(1):1-14. DOI:10.1086/321275.
4. Gabriel SB, Schaffner SF, Nguyen H, et al. The structure of haplotype blocks in the human genome. Science 2002; 296(5576):2225-2229. DOI:10.1126/science.1069424.
5. Price AL, Weale ME, Patterson N, et al. Long-range LD can confound genome scans in admixed populations. American Journal of Human Genetics 2008; 83(1):132-135. DOI:10.1016/j.ajhg.2008.06.005.
6. VanLiere JM, Rosenberg NA. Mathematical properties of the r2 measure of linkage disequilibrium. Theoretical Population Biology 2008; 74(1):130-137. DOI:10.1016/j.tpb.2008.05.006.
7. Rogers AR, Huff C. Linkage disequilibrium between loci with unknown phase. Genetics 2009; 182(3):839-844. DOI:10.1534/genetics.108.093153.
8. Bulik-Sullivan BK, Loh P-R, Finucane HK, et al. LD Score regression distinguishes confounding from polygenicity in genome-wide association studies. Nature Genetics 2015; 47(3):291-295. DOI:10.1038/ng.3211.

## Related Skills

- plink-basics - format conversion and QC before any LD operation
- population-structure - PCA and ADMIXTURE on the LD-pruned marker set
- association-testing - GWAS whose summary statistics feed clumping
- selection-statistics - haplotype statistics that depend on LD structure
- causal-genomics/fine-mapping - resolving independent causal variants beyond clumping
- phasing-imputation/haplotype-phasing - phased haplotypes for EM/haplotype-based r2

## Usage Guide

# Linkage Disequilibrium - Usage Guide

## Overview

Linkage disequilibrium is the non-random association of alleles at different loci, but the practical point is that r2 and D' answer different questions: r2 (= chi2/N) is the tagging and GWAS-power currency, while D' marks whether recombination has been observed and is upward-biased for rare variants; pruning (genotype-blind) and clumping (p-value-aware) are distinct operations, and any clumping or fine-mapping LD reference must be ancestry-matched or it fails silently.

## Prerequisites

- PLINK 1.9 and PLINK 2.0 installed: `conda install -c bioconda plink plink2 vcftools`
- scikit-allel for Python LD: `pip install scikit-allel scipy numpy`
- Input genotypes as BED/BIM/FAM or pgen (PLINK) or VCF (scikit-allel/vcftools); GWAS summary statistics for clumping
- The genome build (hg19 vs hg38) known, since long-range-LD region coordinates are build-specific
- Conceptual prerequisites and big notes:
  - Use r2 for tagging, pruning, imputation, and power; use D' only for block boundaries and recombination history.
  - D'=1 does not imply high r2 - allele-frequency asymmetry caps r2 (r2/r2max = D'^2), so a common SNP cannot tag a rare causal variant.
  - PLINK 2.0 has no bare `--r2`: choose `--r2-unphased` (composite, robust default) or `--r2-phased` (EM, assumes HWE).
  - Pruning (`--indep-pairwise`) eats genotypes and emits an independent marker set; clumping (`--clump`) eats summary statistics plus an LD reference and emits lead SNPs - they are not interchangeable.
  - Exclude long-range-LD regions (MHC, 8p23.1, 17q21.31) by coordinate before pruning or PCA; their internal r2 is high and real.
  - The clumping/fine-mapping/LDSC LD reference must match the study ancestry, ideally the study sample itself.

## Quick Start

Tell your AI agent what you want to do:
- "Prune my genotypes for PCA, excluding long-range-LD regions first"
- "Compute composite r2 between SNPs without phasing"
- "Clump my GWAS summary stats to one lead SNP per locus"
- "Find tag SNPs at r2 >= 0.8 for my variants of interest"
- "Define Gabriel haplotype blocks for a candidate region"
- "Plot LD decay with distance, stratified by population"

## Example Prompts

### LD Pruning
> "Exclude the MHC and known inversions by coordinate, then LD-prune my PLINK fileset at r2 0.1 for PCA."

> "Create an independent SNP set for ADMIXTURE with a 200kb window."

### LD Calculation
> "Compute composite (unphased) r2 between all pairs within 500kb and report D' for the HLA region."

> "Build an LD matrix for my candidate locus and tell me which SNPs tag a variant at r2 >= 0.8."

### GWAS Clumping
> "Clump my GWAS summary statistics with p1 5e-8 and r2 0.1 using an ancestry-matched LD reference."

> "Find lead SNPs for each associated locus, and flag where over-clumping might hide a secondary signal."

### Blocks and Decay
> "Identify Gabriel haplotype blocks across chromosome 6p21."

> "Plot LD decay with physical distance, stratifying by population so admixture LD does not flatten the curve."

## What the Agent Will Do

1. Identify the operation - measure (r2 vs D'), prune, clump, block, or decay - from the stated goal, not from a default.
2. For measurement, default to composite `--r2-unphased` / Rogers-Huff unless phase is trustworthy, and reserve D' for block/recombination questions.
3. For pruning, exclude long-range-LD regions by coordinate first, then slide an r2 window with a step of 1 for kb windows.
4. For clumping, override PLINK's permissive defaults (p1 5e-8, r2 0.1) and use an ancestry-matched LD reference.
5. For blocks, run the Gabriel confidence-interval method; for decay, bin r2 by distance after stratifying by population.
6. Report variant counts before/after pruning, lead SNPs per locus, and any rare-variant or wrong-ancestry caveats.

## Tips

- D'=1 is not "high LD" for prediction; a frequency mismatch makes the proxy useless even at D'=1.
- Do not interpret D' for variants below minor-allele count ~10-20; it is upward-biased and the blocks are sampling artifacts.
- Prefer composite r2 (`--r2-unphased`, Rogers-Huff) when the sample is small, structured, inbred, or has missingness.
- A flat or high-floored LD decay curve is telling about demography (bottleneck, admixture), not distance - stratify first.
- LDSC intercept-minus-1 estimates confounding but absorbs sample overlap; use the attenuation ratio.

## Related Skills

- plink-basics - format conversion and QC before any LD operation
- population-structure - PCA and ADMIXTURE on the LD-pruned marker set
- association-testing - GWAS whose summary statistics feed clumping
- selection-statistics - haplotype statistics that depend on LD structure
- causal-genomics/fine-mapping - resolving independent causal variants beyond clumping
- phasing-imputation/haplotype-phasing - phased haplotypes for EM/haplotype-based r2

## Bundled Files

- `population-genetics--linkage-disequilibrium--examples--ld_analysis.sh` — copied from `examples/ld_analysis.sh`
