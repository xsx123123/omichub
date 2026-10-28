# bio-population-genetics-rare-variant-association

> Bundled component reference for `population-genetics/rare-variant-association` (original source: `skills/bio_skills/population-genetics/rare-variant-association`).

Gene and region-based rare-variant aggregation - burden/collapsing, SKAT, SKAT-O, ACAT-V/ACAT-O, annotation-weighted STAAR - with regenie (--vc-tests), SAIGE-GENE+, and the SKAT R package. Single-variant tests are powerless at low minor allele count, so rare variants are aggregated across a gene or region under an explicit mask (functional class plus a MAF cutoff). A burden test collapses variants into one score assuming a single effect direction (powerful when true, near-zero power when risk and protective variants cancel); SKAT is a variance-component test robust to mixed directions; SKAT-O blends the two; ACAT/STAAR are dependence-robust and annotation-weighted. The mask is the hypothesis, imbalance needs SPA or Firth, and testing burden is per-gene-per-mask. Use when aggregating rare coding or regulatory variants into gene or region tests, choosing burden vs SKAT vs SKAT-O, or building masks. For single-variant GWAS see association-testing; for mask annotations see variant-calling/variant-annotation.

## Instructions

## Version Compatibility

Reference examples tested with: regenie 3.4+, SAIGE 1.3+, SKAT 2.2+ (R), STAAR 0.9.7+ (R).

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

Version traps that change results, not just syntax: regenie `--vc-tests` accepts `skat,skato,skato-acat,acatv,acato,acato-full` (not `skat-o`), `--aaf-bins` upper bounds always add an implicit singleton mask, and `--build-mask` defaults to `max` (one carrier-status column per set) not `sum`. SAIGE-GENE+ `--maxMAF_in_groupTest` takes multiple comma-separated cutoffs in ONE run (the whole point of GENE+ over GENE). The SKAT R package selects SKAT-O with `method="optimal.adj"` or `method="SKATO"`, and `r.corr` is the rho grid (0=SKAT, 1=burden); `weights.beta=c(1,25)` is the rarer-up-weighting default. The single source of truth for versions is this block, not headings.

# Rare-Variant Association

**"Test whether rare variants in this gene associate with my trait"** -> Aggregate the rare variants in a gene or region into one set-based statistic under an explicit mask, because no single rare variant has enough carriers to test alone.
- CLI: `regenie --step 2 --anno-file ... --set-list ... --mask-def ... --aaf-bins 0.01 --vc-tests skato,acato` (biobank masks plus omnibus tests)
- CLI: `step2_SPAtests.R --groupFile ... --annotation_in_groupTest lof,missense;lof --maxMAF_in_groupTest 0.0001,0.001,0.01` (SAIGE-GENE+, imbalance-robust)
- R: `SKAT(Z, obj, method="SKATO", weights.beta=c(1,25))` (direct, small cohorts)

Scope: gene/region-based rare-variant aggregation (burden, SKAT, SKAT-O, ACAT-V/ACAT-O, STAAR), variant masks (functional class plus MAF cutoff), and the per-gene multiple-testing burden. Single-variant GWAS (linear/logistic/LMM/SPA per marker) routes to association-testing. The functional annotations that define masks (LoF, missense, CADD, regulatory) come from variant-calling/variant-annotation. Variant prioritization for clinical interpretation routes to clinical-databases/variant-prioritization.

## The Single Most Important Insight -- a gene-based test is a bet about the direction-of-effect architecture, and the mask IS the hypothesis

1. Single-variant GWAS is underpowered for rare variants because a handful of carriers gives a tiny non-centrality, so signal must be aggregated across a gene or region - and HOW it is aggregated encodes a belief about the unobserved effect architecture.
2. A burden test collapses the set into one direction and is the most powerful test WHEN that holds, but mixing risk and protective variants makes their contributions cancel to a null (false negative); SKAT sums squared scores so directions cannot cancel but is weaker when the truth is unidirectional; SKAT-O optimizes a rho grid between the two and is the default when the architecture is unknown.
3. The MASK is the hypothesis, not a preprocessing detail: which variants enter (LoF-only vs LoF+missense, MAF<0.01 vs <0.001, annotation weights) defines what is being tested, and a different mask is a different question with a different answer - so report the mask, not just the p-value.
4. The aggregate is only as calibrated as the null model: case/control imbalance and low MAC make naive set tests anti-conservative (SAIGE-GENE+ uses SPA, regenie uses Firth/SPA), population structure and relatedness still need an LMM null, and imputed/low-quality variants silently corrupt the mask unless filtered by INFO/R2 and genotype quality first.

## Tool Taxonomy

| Method | Citation | Mechanism | When |
|--------|----------|-----------|------|
| Burden / collapsing (CMC, weighted-sum) | Li & Leal 2008; Madsen & Browning 2009 | Collapse variants into one score, test its single coefficient; assumes one effect direction | Strong prior that variants act the same way (e.g. LoF in a gene) |
| SKAT | Wu 2011 | Variance-component score test on summed squared weighted single-variant scores; directions do not cancel | Mixed directions, or many neutral variants diluting the set |
| SKAT-O | Lee 2012 | Optimal linear combination of burden and SKAT over a rho grid in [0,1]; data choose rho | Unknown architecture - the safe default |
| ACAT-V / ACAT-O | Liu 2019 | Cauchy combination of p-values, calibrated under arbitrary dependence, no permutation/GRM; the smallest p dominates (one artifact can drive it) | Sparse-causal sets, fast omnibus, combining masks/tests |
| STAAR / STAAR-O | Li 2020 | Variance-component test weighting variants by multiple functional annotations (annotation PCs) | WGS regulatory regions where annotations carry the signal |
| SAIGE-GENE+ | Zhou 2022 | LMM null + SPA + variance ratio; multiple MAF cutoffs and annotations in one set test | Biobank binary traits, case/control imbalance, relatedness |
| regenie --vc-tests | Mbatchou 2021 | Whole-genome ridge null (step 1), then masked burden/SKAT/SKAT-O/ACAT in step 2 with Firth/SPA | Biobank pipelines wanting single-variant and gene tests together |

## Decision Tree by Scenario

| Scenario | Use | Why |
|----------|-----|-----|
| Strong prior all variants act one direction (LoF mask) | Burden / collapsing | Most powerful under a true single direction |
| Risk and protective variants expected in the same set | SKAT | Squared scores, directions do not cancel |
| Architecture unknown | SKAT-O | Optimizes rho between burden and SKAT |
| Sparse causal set, or one omnibus across masks | ACAT-V / ACAT-O | Dependence-robust Cauchy combiner, no permutation |
| WGS noncoding where annotations carry the signal | STAAR-O | Multiple functional-annotation weights in one test |
| Biobank, imbalanced binary trait, relatedness | SAIGE-GENE+ | SPA + LMM null keeps the tail calibrated at low MAC |
| One pipeline for single-variant + gene tests at biobank scale | regenie --vc-tests | Shared step-1 null, Firth/SPA in step 2 |
| Small cohort, full control of mask and weights | SKAT R package | Direct, scriptable, SSD files for many sets |

## Build the Mask and Run Aggregate Tests with regenie

**Goal:** test each gene under one or more masks (functional class x MAF cutoff) using burden plus variance-component tests in a biobank-scale pipeline.

**Approach:** reuse the step-1 whole-genome ridge null, then in step 2 define annotations, gene sets, and mask rules and request the omnibus tests, letting Firth handle imbalanced binary traits.

```bash
# Step 1 builds the LOCO whole-genome predictor (the null) once, shared with single-variant GWAS.
regenie --step 1 --bed geno_array --phenoFile pheno.txt --covarFile covar.txt \
    --bsize 1000 --lowmem --out fit_null

# Step 2: --anno-file maps variant -> gene -> annotation; --set-list lists each gene's variants;
# --mask-def names which annotation categories form each mask. --aaf-bins sets the MAF ceilings
# (a singleton mask is always added). --vc-tests requests SKAT-O and the ACAT omnibus alongside
# burden. --firth keeps the imbalanced binary-trait tail calibrated; --build-mask max is the default.
regenie --step 2 --bed geno_wes --phenoFile pheno.txt --covarFile covar.txt \
    --pred fit_null_pred.list --anno-file annot.txt --set-list sets.txt --mask-def masks.txt \
    --aaf-bins 0.001,0.01 --vc-tests skato,acato --build-mask max \
    --bt --firth --approx --pThresh 0.05 --out gene_tests
```

Mask-building file formats (one entry per line, space/tab separated):
- `annot.txt`: `VARIANT_ID GENE ANNOTATION` (e.g. `1:55039839:T:C PCSK9 LoF`); variants with no entry fall in `NULL`.
- `sets.txt`: `GENE CHR POS VARIANT_ID,VARIANT_ID,...` (the gene plus its comma-separated variant list).
- `masks.txt`: `MASK_NAME ANNOTATION,ANNOTATION` (e.g. `Mask_LoF LoF` and `Mask_LoF_mis LoF,missense`).

Run `regenie --step 2 ... --check-burden-files --ignore-pred` first to catch variants in the set-list that are absent from the annotation file (a silent source of empty or wrong masks). `--ignore-pred` is required here because this validation runs before the step-1 predictor exists.

## Imbalance-Robust Set Tests with SAIGE-GENE+

**Goal:** test genes for an imbalanced binary trait in a related sample, scanning several MAF cutoffs and annotation groups in one pass.

**Approach:** fit the SPA-LMM null once (step 1, with a variance ratio), then run the set test passing multiple annotations and multiple max-MAF thresholds so GENE+ combines them.

```bash
# Step 2 set test. --annotation_in_groupTest gives the masks (semicolon-separated groups, each a
# comma-separated annotation list). --maxMAF_in_groupTest passes several MAF cutoffs in ONE run -
# this multi-cutoff combination is exactly what GENE+ adds over the original SAIGE-GENE.
step2_SPAtests.R --bgenFile geno_wes.bgen --groupFile groups.txt \
    --GMMATmodelFile null.rda --varianceRatioFile null.varianceRatio.txt \
    --annotation_in_groupTest "lof;lof,missense;lof,missense,synonymous" \
    --maxMAF_in_groupTest 0.0001,0.001,0.01 --is_output_moreDetails TRUE \
    --SAIGEOutputFile gene_tests.txt
```

The `groups.txt` file gives, per gene, a line of variant IDs and a matching line of their annotations (and optionally a weight line); the annotation labels there must match `--annotation_in_groupTest`.

## Direct SKAT-O in R for a Small Cohort

**Goal:** run burden, SKAT, and SKAT-O on a gene's rare-variant genotype matrix with explicit MAF weighting, for a sample small enough to hold in memory.

**Approach:** fit the null model once on covariates, then call SKAT per gene with the rho grid; for many genes use SSD files keyed by a SetID rather than passing matrices.

```r
library(SKAT)

# Null model on covariates only (out_type='D' binary, 'C' continuous). Refit once, reuse per gene.
obj <- SKAT_Null_Model(phenotype ~ age + sex + PC1 + PC2, out_type = 'D', data = covar_df)

# Z is the n x m genotype matrix (0/1/2) for the m rare variants in one gene.
# weights.beta=c(1,25) is the Beta(MAF;1,25) up-weighting of rarer variants (the SKAT default; the
# Madsen-Browning weight is the gentler Beta(0.5,0.5)). method='SKATO' searches the rho grid (rho=0
# SKAT, rho=1 burden); 'burden' or default SKAT recover the endpoints. r.corr passes an explicit rho grid.
skato <- SKAT(Z, obj, method = 'SKATO', weights.beta = c(1, 25))
burden <- SKAT(Z, obj, r.corr = 1, weights.beta = c(1, 25))
skat <- SKAT(Z, obj, weights.beta = c(1, 25))
c(skato = skato$p.value, burden = burden$p.value, skat = skat$p.value)
```

For genome-wide gene scans, build an SSD file with `Generate_SSD_SetID(bed, bim, fam, SetID, SSD, Info)`, `Open_SSD()`, then `SKAT.SSD.All(SSD.INFO, obj)` to test every set without holding all matrices in memory.

## Per-Method Failure Modes

### Burden test cancels under mixed directions
**Trigger:** a mask mixing risk and protective (or many null) variants. **Mechanism:** the collapsed score sums signed contributions that offset. **Symptom:** near-null p for a gene that SKAT flags strongly. **Fix:** use SKAT or SKAT-O; reserve pure burden for a mask with a real single-direction prior (LoF-only).

### SKAT underpowered when truth is unidirectional
**Trigger:** a clean LoF mask where every variant raises risk. **Mechanism:** the variance-component test spends power on a 2-sided alternative it does not need. **Symptom:** burden hits, SKAT does not. **Fix:** SKAT-O (lets rho->1) or a burden test for that mask.

### Wrong or default mask
**Trigger:** running one default MAF cutoff or an unfiltered annotation set. **Mechanism:** the mask defines the hypothesis; a too-loose MAF or LoF+benign-missense mask dilutes signal with noise. **Symptom:** a true gene disappears under one mask, appears under another. **Fix:** test a small grid of masks (LoF, LoF+missense; MAF 0.001, 0.01) and combine with ACAT-O, accounting for the masks in the burden.

### Uncalibrated tail under case/control imbalance
**Trigger:** a naive set test on an imbalanced binary trait at low MAC. **Mechanism:** the score statistic's normal/chi-square null is wrong in the tail. **Symptom:** anti-conservative gene p-values, inflated QQ for rare masks. **Fix:** SAIGE-GENE+ (SPA) or regenie `--firth`/`--spa`; never a plain score test here.

### Residual structure/relatedness in the null
**Trigger:** aggregating in a structured or related sample with a fixed-effect-only null. **Mechanism:** relatedness is a covariance structure PCs cannot remove. **Symptom:** genome-wide gene inflation that PCs do not fix. **Fix:** an LMM null (SAIGE-GENE+, regenie step-1 LOCO predictor) before the set test.

### Imputed/low-quality variants in the mask
**Trigger:** building masks from imputed or low-callrate genotypes. **Mechanism:** miscalled rare variants add spurious carriers. **Symptom:** unreplicable gene hits driven by a few low-quality sites. **Fix:** filter by INFO/R2 (>=0.8 for rare) and genotype quality before masking; prefer sequenced calls for rare-variant sets.

## Quantitative Thresholds

| Quantity | Typical value | Rationale |
|----------|---------------|-----------|
| "Rare" MAF cutoff for aggregation | MAF < 0.01 (< 0.001 for LoF-only) | below this single-variant power collapses; aggregate instead |
| Mask MAF tiers | 0.0001 / 0.001 / 0.01 | nested AAF bins capture ultra-rare and rare jointly (regenie `--aaf-bins`, SAIGE `--maxMAF_in_groupTest`) |
| Exome-wide gene significance | ~2.5e-6 | Bonferroni 0.05 over ~20,000 genes; tighten further for multiple masks per gene |
| Per-mask multiple testing | divide by (genes x masks) or combine masks via ACAT-O | each mask is a separate test unless an omnibus absorbs them |
| Ultra-rare collapsing (MAC) | collapse MAC < ~10 into one pseudo-variant | regenie `--vc-MACthr` default 10; SAIGE-GENE+ collapses ultra-rare for calibration |
| Imputed-variant quality for masks | INFO/R2 >= 0.8 (rare) | rare imputed dosages are noisy; lenient 0.3 cutoffs corrupt masks |
| SKAT MAF weighting | Beta(MAF; 1, 25) | `weights.beta=c(1,25)` up-weights rarer variants (Wu 2011 default) |

Thresholds are conventions; inspect the per-gene QQ plot and verify current best practice before applying numbers blindly.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| regenie `--vc-tests skat-o` unrecognized | wrong token | use `skato` (and `acato`, `acatv`, `skato-acat`); not `skat-o` |
| Empty or tiny masks, genes silently dropped | variants in set-list absent from anno-file | run `--check-burden-files` first; harmonize variant IDs |
| Inflated gene QQ for an imbalanced trait | plain score test, no SPA/Firth | SAIGE-GENE+ or regenie `--firth`/`--spa` |
| SKAT-O not actually run in R | passing `method="SKAT"` or omitting it | `method="SKATO"` or `"optimal.adj"`; `r.corr=1` is pure burden |
| Single MAF cutoff misses ultra-rare signal | one `--aaf-bins`/`--maxMAF` value | pass nested cutoffs (0.0001,0.001,0.01) in one run |
| Same single-variant p reported as "gene" | testing markers, not a set | confirm a set/group file is supplied and the test is set-based |
| Gene hit driven by one artifactual variant | ACAT/burden dominated by a miscalled site | QC inputs (INFO/R2, genotype quality) before aggregating |

## References

1. Li B, Leal SM. Methods for detecting associations with rare variants for common diseases: application to analysis of sequence data. American Journal of Human Genetics 2008; 83(3):311-321. DOI:10.1016/j.ajhg.2008.06.024.
2. Madsen BE, Browning SR. A groupwise association test for rare mutations using a weighted sum statistic. PLoS Genetics 2009; 5(2):e1000384. DOI:10.1371/journal.pgen.1000384.
3. Wu MC, Lee S, Cai T, Li Y, Boehnke M, Lin X. Rare-variant association testing for sequencing data with the sequence kernel association test. American Journal of Human Genetics 2011; 89(1):82-93. DOI:10.1016/j.ajhg.2011.05.029.
4. Lee S, Emond MJ, Bamshad MJ, et al. Optimal unified approach for rare-variant association testing with application to small-sample case-control whole-exome sequencing studies. American Journal of Human Genetics 2012; 91(2):224-237. DOI:10.1016/j.ajhg.2012.06.007.
5. Liu Y, Chen S, Li Z, Morrison AC, Boerwinkle E, Lin X. ACAT: a fast and powerful p value combination method for rare-variant analysis in sequencing studies. American Journal of Human Genetics 2019; 104(3):410-421. DOI:10.1016/j.ajhg.2019.01.002.
6. Li X, Li Z, Zhou H, et al. Dynamic incorporation of multiple in silico functional annotations empowers rare variant association analysis of large whole-genome sequencing studies at scale. Nature Genetics 2020; 52(9):969-983. DOI:10.1038/s41588-020-0676-4.
7. Mbatchou J, Barnard L, Backman J, et al. Computationally efficient whole-genome regression for quantitative and binary traits. Nature Genetics 2021; 53(7):1097-1103. DOI:10.1038/s41588-021-00870-7.
8. Zhou W, Bi W, Zhao Z, et al. SAIGE-GENE+ improves the efficiency and accuracy of set-based rare variant association tests. Nature Genetics 2022; 54(10):1466-1469. DOI:10.1038/s41588-022-01178-w.

## Related Skills

- association-testing - single-variant GWAS (linear/logistic/LMM/SPA per marker) that this skill aggregates beyond
- plink-basics - genotype QC and format conversion before masking
- population-structure - PCs and relatedness for the null model that calibrates the set test
- variant-calling/variant-annotation - functional annotations (LoF, missense, CADD, regulatory) that define masks
- clinical-databases/variant-prioritization - clinical interpretation of variants flagged by gene tests
- causal-genomics/fine-mapping - resolving which variants in a significant gene/region carry the signal

## Usage Guide

# Rare-Variant Association - Usage Guide

## Overview

Rare variants have too few carriers for single-variant GWAS to detect, so the unit of analysis becomes a gene or region and the question becomes which aggregation test to use. That choice is a bet about the unobserved effect architecture: a burden test assumes every variant in the mask acts in the same direction and is most powerful when that holds but cancels to a null under mixed directions, SKAT is a variance-component test robust to mixed directions but weaker when the truth is unidirectional, and SKAT-O optimally blends the two. The mask - which variants enter, by functional class and MAF cutoff - is the hypothesis, not a preprocessing detail, and the null model (SPA/Firth for imbalance, an LMM for relatedness) is what keeps the aggregate calibrated.

## Prerequisites

- regenie (`conda install -c bioconda regenie`) and/or SAIGE (`conda install -c bioconda saige`) for biobank-scale set tests
- The SKAT and STAAR R packages (`install.packages('SKAT')`; STAAR from `xihaoli/STAAR` via remotes) for direct/scriptable analysis
- QC'd genotypes (sequenced calls preferred for rare-variant masks) and per-variant functional annotations (LoF, missense, CADD, regulatory)
- Covariates (age, sex, principal components) and, for related samples, the inputs to fit an LMM null
- Conceptual prerequisites and big notes:
  - The mask (functional class x MAF cutoff) IS the hypothesis; report it alongside any p-value and test a small grid of masks rather than one default.
  - Burden assumes one effect direction; SKAT does not; SKAT-O picks between them. Pick from the architecture prior, not habit.
  - Case/control imbalance and low MAC make naive set tests anti-conservative; use SPA (SAIGE-GENE+) or Firth (regenie).
  - Population structure and relatedness still need an LMM null; PCs alone cannot remove relatedness.
  - The multiple-testing burden is per-gene-per-mask (exome-wide ~2.5e-6, tighter with multiple masks); combine masks via ACAT-O to limit it.
  - Imputed or low-callrate variants corrupt masks; filter by INFO/R2 and genotype quality first.

## Quick Start

Tell your AI agent what you want to do:
- "Run gene-based burden, SKAT, and SKAT-O tests on my exome data"
- "Build LoF-only and LoF+missense masks at MAF 0.001 and 0.01 and test each gene"
- "Use SAIGE-GENE+ for an imbalanced binary trait in a related cohort"
- "Run regenie gene tests with the SKAT-O and ACAT-O omnibus and Firth fallback"
- "Decide whether burden or SKAT fits my gene's effect architecture"
- "Set an exome-wide significance threshold for my gene tests"

## Example Prompts

### Test selection
> "I have a gene with both predicted gain-of-function and loss-of-function rare variants - which aggregation test should I run, and why not a plain burden test?"

### Biobank pipeline
> "Run regenie step 2 gene-based tests on my whole-exome data with LoF and LoF+missense masks at AAF 0.001 and 0.01, request SKAT-O and ACAT-O, and turn on Firth for the imbalanced binary trait."

### Imbalance and relatedness
> "My case:control ratio is 1:50 and the sample has cryptic relatedness - set up SAIGE-GENE+ to test each gene across MAF cutoffs 0.0001, 0.001, and 0.01."

### Direct R analysis
> "For a small case-control cohort, fit a SKAT null model on covariates and report burden, SKAT, and SKAT-O p-values for one gene with Beta(1,25) MAF weighting."

### Masks and thresholds
> "Explain how to build the annotation, set-list, and mask-definition files for regenie and what exome-wide significance threshold to use across multiple masks."

## What the Agent Will Do

1. Confirm the scope is gene/region aggregation, not single-variant GWAS (which routes to association-testing), and identify the trait type and sample structure.
2. Choose the engine: regenie or SAIGE-GENE+ for biobank scale (SAIGE-GENE+ when imbalance/relatedness dominate), or the SKAT R package for small scriptable cohorts.
3. Build the variant masks from functional annotations and MAF cutoffs, treating the mask as the hypothesis and testing a small grid rather than one default.
4. Select the test from the architecture prior: burden for a single-direction mask, SKAT for mixed directions, SKAT-O when unknown, ACAT-O/STAAR for omnibus or annotation-weighted analysis.
5. Calibrate the null: SPA/Firth for imbalance, an LMM null (LOCO predictor or sparse GRM) for relatedness, and QC out imputed/low-quality variants first.
6. Set the per-gene-per-mask significance threshold (exome-wide ~2.5e-6, tighter with multiple masks or combined via ACAT-O) and report the mask with each result.

## Tips

- Validate mask inputs before running: regenie `--check-burden-files` flags set-list variants missing from the annotation file, a silent cause of empty masks.
- Pass nested MAF cutoffs in one run (regenie `--aaf-bins 0.0001,0.001,0.01`, SAIGE `--maxMAF_in_groupTest 0.0001,0.001,0.01`) rather than rerunning per cutoff.
- A burden hit with a null SKAT (or vice versa) is diagnostic of the architecture, not a contradiction - report both and let SKAT-O/ACAT-O adjudicate.
- ACAT-O is dominated by its smallest input p-value by design, so a single artifactual variant can drive a gene; QC the inputs (INFO/R2, genotype quality) before trusting a hit.
- Reuse the step-1 null across single-variant and gene tests (regenie, SAIGE) so the relatedness/structure model is identical for both.
- For genome-wide gene scans in R, use SSD files (`Generate_SSD_SetID`, `Open_SSD`, `SKAT.SSD.All`) instead of holding every gene's matrix in memory.

## Related Skills

- association-testing - single-variant GWAS (linear/logistic/LMM/SPA per marker) that this skill aggregates beyond
- plink-basics - genotype QC and format conversion before masking
- population-structure - PCs and relatedness for the null model that calibrates the set test
- variant-calling/variant-annotation - functional annotations (LoF, missense, CADD, regulatory) that define masks
- clinical-databases/variant-prioritization - clinical interpretation of variants flagged by gene tests
- causal-genomics/fine-mapping - resolving which variants in a significant gene/region carry the signal

## Bundled Files

- `population-genetics--rare-variant-association--examples--rare_variant_test.sh` — copied from `examples/rare_variant_test.sh`
