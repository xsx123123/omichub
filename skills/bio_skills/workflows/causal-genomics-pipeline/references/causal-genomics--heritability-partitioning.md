# bio-causal-genomics-heritability-partitioning

> Bundled component reference for `causal-genomics/heritability-partitioning` (original source: `skills/bio_skills/causal-genomics/heritability-partitioning`).

Estimates SNP heritability and partitions it across functional annotations, cell types, and loci from GWAS summary statistics or individual-level genotypes. Implements LDSC, stratified LDSC with the baseline-LD model, Finucane 2018 cell-type prioritization, LDAK SumHer, HDL, HESS local heritability, BOLT-REML, GCTA-GREML, graphREML, and Popcorn cross-population genetic correlation. Use when computing total h2_SNP from summary stats, partitioning heritability across functional categories, prioritizing trait-relevant tissues or cell types from ENCODE/Roadmap chromatin marks, reconciling LDSC vs LDAK enrichment estimates, computing local heritability with HESS, estimating genetic correlation between traits, or producing publication-grade enrichment with calibrated sensitivity to model assumptions.

## Instructions

## Version Compatibility

Reference examples tested with: LDSC v1.0.1+ (Python 3 fork; prefer `abdenlab/ldsc-python3` v2.0.0 which retains the working `--h2 / --rg / --h2-cts` CLI -- `belowlab/ldsc` v3.0.1 explicitly broke that CLI per its README and is best run via Docker `jtb114/ldsc:latest`), LDAK 6.0+, BOLT-LMM 2.4.1+, GCTA 1.94+, HESS 0.5.4+, HDL 1.4.0+ (R; GitHub `zhenin/HDL`), Popcorn 1.0+ (Python; brielin/Popcorn), baselineLD_v2.2 annotations (alkesgroup.broadinstitute.org/LDSCORE).

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `python -c 'import <module>; help(<module>)'`
- R: `packageVersion('<pkg>')` then `?function_name`
- CLI: `<tool> --version` then `<tool> --help`

LDSC's official repository (bulik/ldsc) is Python 2.7 only and unmaintained since 2019; use the Python 3 community forks. If code throws ImportError, AttributeError, or a "category not found" error in the LD score file, introspect the installed binary and the actual LD-score column headers rather than retrying.

# Heritability Partitioning

**"Estimate SNP heritability and partition it across functional categories, cell types, and loci"** -> Decompose `h2_SNP` from GWAS summary statistics (or individual-level genotypes) into contributions from baseline annotations (coding, conserved, regulatory), tissue-specific chromatin marks, and per-locus components, then reconcile model-dependent enrichment estimates across LDSC and LDAK. Tool choice is a decision about the **regime** (summary-stat vs individual-level; one-trait vs two-trait genetic correlation; total vs partitioned vs local) and the **model assumption** about how per-SNP heritability scales with LD, MAF, and functional annotation (GCTA model vs LDAK-Thin vs baseline-LD).

- CLI (h2 from sumstats, EUR): `ldsc.py --h2 trait.sumstats.gz --ref-ld-chr eur_w_ld_chr/ --w-ld-chr eur_w_ld_chr/ --out h2`
- CLI (functional partitioning): `ldsc.py --h2 trait.sumstats.gz --ref-ld-chr baselineLD.,<annot>. --frqfile-chr 1000G.EUR.QC. --w-ld-chr weights. --overlap-annot --print-coefficients --out part`
- CLI (cell-type prioritization, Finucane 2018): `ldsc.py --h2-cts trait.sumstats.gz --ref-ld-chr-cts <cts_file>.ldcts --w-ld-chr weights. --out cts`
- CLI (cross-trait rg): `ldsc.py --rg t1.sumstats.gz,t2.sumstats.gz --ref-ld-chr eur_w_ld_chr/ --w-ld-chr eur_w_ld_chr/ --out rg`
- CLI (LDAK alternative): `ldak --sum-hers <out> --summary trait.txt --tagfile ldak.thin.<build>.tagging --check-sums NO`
- R (HDL): `HDL::HDL.rg(gwas1.df, gwas2.df, LD.path = 'UKB_array_SVD_eigen90_extraction')`
- CLI (local h2): HESS step1 `hess.py --local-hsqg trait.sumstats.gz --chrom <chr> --bfile <ref> --partition <part>.bed --out hess_<chr>`

## Statistical Model Taxonomy

| Method | Heritability model | Input | Output | Strength | Fails when |
|--------|--------------------|-------|--------|----------|------------|
| LDSC h2 (Bulik-Sullivan 2015 Nat Genet 47:291) | GCTA model: per-SNP h2 proportional to LD score | Sumstats + ancestry-matched LD scores | h2 estimate + intercept + ratio | Standard for sumstats; fast; calibrated EUR LD scores | N too low (mean chi-square < 1.02); non-EUR ancestry with EUR LD scores; population stratification not captured |
| Stratified LDSC / S-LDSC (Finucane 2015 Nat Genet 47:1228) | GCTA model with per-annotation tau coefficients | Sumstats + baseline + custom annotations | Per-annotation enrichment + tau | Reference functional partitioning method | Highly collinear annotations inflate per-tau SE; small annotation (<0.5% genome) underpowered |
| Baseline-LD model (Gazal 2017 Nat Genet 49:1421) | Adds LD-related and MAF-dependent annotations to baseline | Sumstats + `baselineLD_v2.2.` | Enrichment robust to LD-MAF confounding | Modern S-LDSC default; calibrates LD/MAF dependence | EUR-only baseline-LD v2.2 must NOT be used on non-EUR GWAS; use baseline-LD-X / S-LDXR (Shi H & Gazal S et al 2021 Nat Commun 12:1098) instead |
| Cell-type S-LDSC (Finucane 2018 Nat Genet 50:621) | Per-cell-type annotation marginal to baseline | Sumstats + cell-type chromatin annotations (.ldcts) | Per-cell-type p-value | Tissue / cell-type prioritization; published per-tissue ldcts files | Sample size small (mean chi-square < 1.02); annotation overlaps strongly with baseline |
| HDL (Ning 2020 Nat Genet 52:859) | Genome-wide eigen-decomposition likelihood | Sumstats + HDL reference panel (UKB N=336k) | h2 and rg with ~60% lower variance than LDSC | Equivalent to ~2.5x sample size for h2 / rg | Sample overlap > 5% biases the likelihood; only EUR HDL reference panel publicly available; no non-EUR HDL eigen-reference exists as of 2026 -- for non-EUR fall back to ancestry-matched cross-trait LDSC (intercept absorbs overlap; rg unbiased) |
| LDAK SumHer (Speed 2019 Nat Genet 51:277) | LDAK-Thin model: per-SNP h2 reweighted by MAF + LD | Sumstats + LDAK-Thin tagging file | h2 + enrichment | Alternative to LDSC; often better-fitting per cross-validation per Speed 2017 Nat Genet 49:986 | Tagging file must match build / ancestry; non-EUR support limited |
| HESS (Shi 2016 AJHG 99:139; Shi 2017 AJHG 101:737) | Per-locus h2 via quadratic form on LD-projected effect estimates | Sumstats + LD reference + locus partition (LDetect) | Per-locus h2 + bivariate local rg | Locus-level resolution; identifies high-h2 loci for follow-up | Locus has < 1000 SNPs; LD reference must be in-sample or matched |
| BOLT-REML (Loh 2015 Nat Genet 47:1385) | Bayesian REML; multi-component variance | Individual-level genotypes (PLINK BED) + phenotype | h2 + per-component partition | Biobank-scale (N=500k feasible); more precise than LDSC at high N | Needs individual-level data; assumes Gaussian residual; not for case-control < 5% prevalence without LMM-BOLT |
| GCTA-GREML (Yang 2011 AJHG 88:76) | GRM-based REML on individual genotypes | GRM (PLINK BED) + phenotype + covariates | h2 + SE | Gold standard for individual-level data; PCGC for case-control | N <= 5000 has wide SE; case-control needs PCGC-S correction; population stratification leaks into h2 |
| graphREML (Li H et al 2024 medRxiv 2024.11.04.24316716; published Nat Genet 2026) | Sumstat REML using LDGM graph | Sumstats + LDGM reference | h2 + functional partition | Use when an LDGM reference exists for the ancestry AND runtime matters at biobank N (> 200k); pre-built LDGM panels currently cover EUR + EAS | Newer (2024); reference panel availability evolving; non-EUR/EAS ancestries lack pre-built LDGM |
| Popcorn (Brown 2016 AJHG 99:76) | Trans-ancestry genetic correlation under MAF-LD model | Sumstats + cross-population LD scores | rg trans-ancestry + h2 per population | Distinguishes shared-causal vs ancestry-specific signal | Effective N per population must be > 5000; small non-EUR cohorts unstable |
| Cross-model reconciliation (Gazal 2019 Nat Genet 51:1202) | Joint LDSC + LDAK comparison framework | Both LDSC and LDAK outputs | Enrichment model-comparison (Gazal: baseline-LD better-calibrated; LDAK developers dispute) | Quantifies model-dependent component of enrichment | Methodological / reporting practice, not a separate primary estimator |

Methodology evolves; benchmark consensus shifts. Verify against current Yengo 2022 *Nat Methods*, Speed D, Holmes J & Balding DJ 2020 Nat Genet 52:458 (heritability model comparison), and the alkesgroup/Price Lab tutorial (LDSC) before locking method as primary. Per-SNP-h2 model choice is an open debate; report both LDSC and LDAK SumHer when a claim depends on model assumption.

## Decision Tree by Scenario

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Total h2 from sumstats, EUR GWAS, N > 50k | LDSC h2 | Standard, fast, well-calibrated against EUR reference |
| Partitioned h2 by functional category | S-LDSC with baseline-LD_v2.2 | Default functional partitioning; LD/MAF-robust |
| Tissue / cell-type prioritization | S-LDSC --h2-cts with ENCODE/Roadmap or scATAC ldcts | Designed for this; per-tissue Bonferroni-controlled |
| Two-trait genetic correlation from sumstats, no overlap | HDL (primary) + cross-trait LDSC (secondary) | HDL ~60% lower variance; LDSC robust under any overlap |
| Two-trait rg with sample overlap > 5% | Cross-trait LDSC | HDL biased by overlap; LDSC intercept absorbs overlap |
| Individual-level biobank h2, N > 100k | BOLT-REML | Better precision; multi-component partition |
| Smaller individual-level cohort, N 5-50k | GCTA-GREML | Gold-standard REML; PCGC if case-control < 20% prevalence |
| Local heritability and bivariate local rg | HESS | Per-locus resolution; identifies hotspots for follow-up |
| Trans-ancestry rg / cross-population h2 | Popcorn | Designed for trans-ethnic; LD scores per population |
| Functional enrichment claim depends on model | Report BOTH LDSC and LDAK SumHer | Per Gazal 2019; model-dependence is real |
| Case-control GWAS with low prevalence | LDSC on liability scale (--samp-prev --pop-prev) | Observed-scale h2 understates liability-scale truth |
| Single-cell ATAC cell-type prioritization | S-LDSC with per-cluster ATAC peaks as annotations | Cross-reference atac-seq/single-cell-atac for peak generation |

## LDSC Intercept Interpretation (Postdoc Nuance)

The LDSC intercept is widely misinterpreted as a "confounding score". The correct interpretation:

- Intercept = 1 indicates no inflation from population structure, cryptic relatedness, or sample overlap (idealised)
- Intercept > 1 indicates SOME source of inflation, BUT polygenic background can elevate the intercept too: at very high N, polygenic signal can lift the intercept modestly without stratification
- The **ratio** statistic `ratio = (intercept - 1) / (mean_chi2 - 1)` is the fraction of inflation attributable to non-polygenic sources; a ratio of 0 means all inflation is polygenic, a ratio near 1 means most of it is stratification or overlap
- Bulik-Sullivan 2015 recommends interpreting intercept jointly with mean chi-square; intercept of 1.05 is innocuous if mean chi-square is 1.5 (ratio = 0.1) but worrying if mean chi-square is 1.05 (ratio = 1.0)

**Operational rule:** Always report intercept, mean chi-square, and ratio together. Do not interpret intercept in isolation. For sample-overlap diagnosis between two GWAS, use bivariate LDSC intercept, not univariate.

**Intercept > 1.5 troubleshooting ladder** (work in order; stop when source is found): (a) per-cohort PC adjustment was insufficient; refit GWAS with more PCs (10-20) or per-cohort separately, (b) cryptic relatedness in the GWAS cohort -- run `king --related` and remove pairs with kinship > 0.05 (or 0.0884 for second-degree), (c) case-control matching imbalance -- check case/control PCs separately, (d) sample-overlap with one of the contributing cohorts (especially in meta-analysis) -- check bivariate intercepts pairwise, (e) if biobank-internal, recompute the GWAS with sample-level relatedness exclusion before LDSC.

## LDSC vs LDAK Reconciliation

LDSC (GCTA model) and LDAK SumHer (LDAK-Thin model) make different assumptions about how per-SNP heritability scales with LD and MAF:

- **GCTA model (LDSC default):** per-SNP h2 inversely proportional to local LD score; high-LD SNPs tag many causal variants
- **LDAK-Thin (Speed 2017 Nat Genet 49:986-992 introduced the LDAK model; the Thin model was formalized in Speed 2020 Nat Genet 52:458):** per-SNP h2 weighted by MAF and inversely by LD with empirical exponents; less weight on common high-LD SNPs

These give systematically different functional enrichment estimates. Speed 2019 reported that LDAK-Thin often gives **lower** conserved-region enrichment than baseline LDSC; conversely LDSC can over-attribute h2 to coding/conserved regions because the GCTA prior couples LD to causality. Gazal 2019 Nat Genet 51:1202-1204 argues the baseline-LD S-LDSC model is better-calibrated (higher model likelihood) and that LDAK/SumHer's lower functional-enrichment estimates are downward-biased; the LDAK developers dispute this (Speed 2020 Nat Genet 52:458), so report both models and flag the model-dependence.

**Operational rule:** Whenever functional enrichment is the primary claim (e.g. "h2 is enriched in tissue T by N-fold"), report enrichment from BOTH LDSC and LDAK. Flag the model assumption. If LDSC and LDAK disagree by > 2x, treat the claim as model-dependent and cite Gazal 2019. For non-enrichment claims (total h2, rg between two traits), the model dependence is smaller and LDSC alone is acceptable.

## Cell-Type Prioritization (Finucane 2018)

Finucane 2018 Nat Genet 50:621 introduced cell-type-specific S-LDSC: partition heritability against ENCODE / Roadmap chromatin marks (H3K4me3, H3K27ac, H3K4me1, DNase, ATAC) tissue-by-tissue, retain per-tissue p-value adjusting for the baseline model. Trait-relevant tissue = top-ranked tissue with p < 0.05/N_tissues (Bonferroni for ~200 tissues, threshold ~2.5e-4).

**Goal:** Rank tissues / cell types by their per-annotation contribution to trait heritability.

**Approach:** Build per-cell-type LD scores from chromatin-marker BED files; compile `.ldcts` manifest (one row per cell type: name, ldscore prefix, control ldscore); run `--h2-cts` and interpret per-cell-type coefficient p-value.

```bash
# Cell-type prioritization example workflow (Finucane 2018)
# Inputs: trait.sumstats.gz (munged), <cts>.ldcts manifest, baseline annotations,
#         eur_w_ld weights, 1000G EUR frequency files

ldsc.py \
    --h2-cts trait.sumstats.gz \
    --ref-ld-chr 1000G_EUR_Phase3_baseline/baseline. \
    --ref-ld-chr-cts Multi_tissue_chromatin.ldcts \
    --w-ld-chr weights_hm3_no_hla/weights. \
    --out trait_cts
# trait_cts.cell_type_results.txt: Name, Coefficient, Coefficient_std_error, Coefficient_P_value
# Apply Bonferroni at 0.05 / nrow; top tissues are trait-relevant
```

Published `.ldcts` files cover GTEx tissues, Roadmap epigenome, immune cell types, and scATAC clusters. Custom .ldcts for novel cell types requires computing per-cell-type LD scores from a chromatin BED via `ldsc.py --l2 --bfile ... --annot <cell>.annot.gz`.

## Quantitative Thresholds

| Threshold | Source | Rationale |
|-----------|--------|-----------|
| mean chi-square > 1.02 | LDSC wiki / Bulik-Sullivan 2015 | Below this, LDSC h2 estimate has huge SE; need N proportional to 1 / h2 |
| h2 SE < 0.02 | LDSC convention | Below this SE, h2 estimate is interpretable; above, treat as exploratory |
| h2 SE >= 0.02 OR mean chi-square < 1.02 | LDSC convention | Estimate unreliable; N >= 50k is typical noise floor for h2 ~ 0.1 (scales as ~1/h2) |
| LDSC intercept in (1, 1.5] | Bulik-Sullivan 2015 | Mild inflation acceptable; report ratio |
| LDSC intercept > 1.5 | -- | Substantial inflation; investigate stratification / overlap before interpreting h2 |
| LDSC ratio < 0.2 | Bulik-Sullivan 2015 | Most inflation is polygenic; estimate is trustworthy |
| Stratified LDSC enrichment p < 0.05 / N_annot | Finucane 2015 | Bonferroni across annotations in the baseline-LD model |
| S-LDSC cell-type p < 2.5e-4 | Finucane 2018; ~200 tissues | Bonferroni for tissue prioritization |
| HESS h2 per locus needs >= 1000 SNPs | Shi 2017 AJHG 101:737 | Quadratic form unstable below this density |
| HDL sample overlap < 5% | Ning 2020 Nat Genet 52:859 | Above 5%, HDL likelihood is biased |
| LDAK tagging file build match | Speed 2019 | hg19 vs hg38 tagging files non-interchangeable |
| Annotation > 0.5% of genome | Finucane 2015 | Smaller categories underpowered for tau estimation |
| Effective N > 5000 per population (Popcorn) | Brown 2016 AJHG 99:76 | Below this, trans-ancestry rg has very wide CI |

## LDSC Standard Workflow

**Goal:** Compute total h2 plus partitioned heritability across functional categories from EUR GWAS summary statistics.

**Approach:** Munge sumstats to LDSC format -> run --h2 for total -> run --h2 with --ref-ld-chr including baseline annotations -> --overlap-annot for enrichment p-values -> --print-coefficients for per-annotation tau.

```bash
# 1. Munge GWAS summary statistics into LDSC format
munge_sumstats.py \
    --sumstats gwas_raw.tsv \
    --N-col N \
    --snp SNP --a1 A1 --a2 A2 --p P --signed-sumstats BETA,0 \
    --merge-alleles w_hm3.snplist \
    --out trait
# Produces trait.sumstats.gz with SNP, A1, A2, Z, N columns

# 2. Total h2 (univariate; intercept, ratio, mean chi2 reported)
ldsc.py \
    --h2 trait.sumstats.gz \
    --ref-ld-chr eur_w_ld_chr/ \
    --w-ld-chr eur_w_ld_chr/ \
    --out trait_h2

# 3. Partitioned h2 with baseline-LD v2.2 model (Gazal 2017)
ldsc.py \
    --h2 trait.sumstats.gz \
    --ref-ld-chr 1000G_Phase3_baselineLD_v2.2_ldscores/baselineLD. \
    --frqfile-chr 1000G_Phase3_frq/1000G.EUR.QC. \
    --w-ld-chr 1000G_Phase3_weights_hm3_no_MHC/weights.hm3_noMHC. \
    --overlap-annot \
    --print-coefficients \
    --out trait_partitioned
```

Ancestry-matched LD scores (EAS, AFR, AMR) are available at alkesgroup.broadinstitute.org/LDSCORE; do NOT apply EUR LD scores to non-EUR GWAS.

## Cross-Trait LDSC for Genetic Correlation

**Goal:** Estimate genetic correlation `rg` between two traits with calibrated handling of sample overlap.

**Approach:** Munge both sumstats with identical SNP list -> run --rg with two munged files; the bivariate intercept absorbs sample overlap and the rg estimate remains unbiased.

```bash
ldsc.py \
    --rg trait1.sumstats.gz,trait2.sumstats.gz \
    --ref-ld-chr eur_w_ld_chr/ \
    --w-ld-chr eur_w_ld_chr/ \
    --out rg
# Output: rg, se, p, gcov_int (cross-trait intercept), h2_obs, h2_int per trait
```

The cross-trait intercept (`gcov_int`) is the LDSC analog of sample-overlap z-score correlation; non-zero indicates sample overlap or cryptic shared structure. LDSC rg is unbiased even with sample overlap because the bivariate intercept absorbs it. HDL is more precise but requires non-overlapping samples.

Non-zero `gcov_int` under known sample overlap is the **correct** behavior, NOT pathology. The rg estimate remains unbiased; the intercept is the overlap absorber, doing its job. Pre-empt the reviewer comment "gcov_int = 0.05 with a shared cohort is expected, not confounding evidence" by reporting `gcov_int` alongside rg and explaining the absorber role.

## Per-Method Failure Modes

### LDSC intercept misinterpretation

**Trigger:** Reporting intercept ~1.05 as "evidence of confounding".

**Mechanism:** Intercept absorbs mean chi-square inflation from any non-polygenic source PLUS some polygenic contribution at very high N. In isolation, intercept above 1 does not imply confounding.

**Symptom:** Methods section claims population stratification based solely on intercept value; reviewers flag the omission of ratio statistic.

**Fix:** Always report intercept, mean chi-square, ratio = (intercept - 1) / (mean_chi2 - 1), and h2 jointly. Interpret ratio < 0.2 as "mostly polygenic, h2 trustworthy"; ratio > 0.3 as "investigate population structure / overlap before claiming h2".

### LDSC vs LDAK enrichment discordance

**Trigger:** Running both LDSC baseline-LD and LDAK SumHer and getting different per-annotation enrichment.

**Mechanism:** GCTA model (LDSC) couples per-SNP h2 to local LD; LDAK-Thin de-couples and re-weights by MAF + LD with empirical exponents. These priors differ; the data alone cannot determine which is correct.

**Symptom:** LDSC reports conserved-region enrichment of 25x; LDAK reports 10x; both are model-internally consistent.

**Fix:** Cite Gazal 2019 Nat Genet 51:1202 as the LDSC-vs-LDAK reconciliation reference; report BOTH models; treat 2x or larger discordance as model-dependent. For enrichment-driven hypotheses (e.g. tissue prioritization), reconcile by reporting LDSC primary + LDAK confirmatory and emphasize directional agreement over magnitude. Do not pick the model that gives the desired answer.

### HDL bias with sample overlap

**Trigger:** Running HDL.rg on two GWAS that share > 5% of samples (e.g. two UKB traits, or UKB + FinnGen with overlapping recruitment).

**Mechanism:** HDL's eigen-decomposition likelihood treats the two traits as independent samples; sample-correlation in residuals biases the likelihood (typically inflates rg toward 1).

**Symptom:** HDL rg substantially different from cross-trait LDSC rg; HDL z-score very large compared to LDSC z; suspicious for high-correlation trait pairs.

**Fix:** Use cross-trait LDSC instead (intercept absorbs overlap). If both must be used, restrict HDL to unambiguously non-overlapping cohorts (e.g. UKB-only trait1 vs FinnGen-only trait2 with no shared individuals confirmed via individual ID exchange or IBD).

### LDSC with non-EUR ancestry and EUR LD scores

**Trigger:** Applying default EUR LD scores from `alkesgroup.broadinstitute.org/LDSCORE/eur_w_ld_chr/` to an EAS, AFR, or AMR GWAS.

**Mechanism:** LD-score regression assumes the LD-score covariate matches the GWAS population's LD structure. Cross-ancestry application produces biased h2 (typically underestimates) and inflated intercept.

**Symptom:** h2 estimate < 0.05 despite trait being known-heritable from twin / family studies; intercept > 1.2 with non-polygenic mean chi-square; ratio > 0.5.

**Fix:** Use ancestry-matched LD scores (EAS, AFR, AMR available at the same Alkes group URL). If multi-ancestry meta-analysis, use Popcorn or trans-ancestry MAMA framework rather than LDSC on the combined sumstats.

### Stratified LDSC with collinear annotations

**Trigger:** Adding a custom annotation that overlaps heavily with an existing baseline category (e.g. "active promoter" against "promoter").

**Mechanism:** Per-annotation tau coefficients are estimated jointly via multivariable regression; collinearity inflates per-tau SE and can flip the sign of marginal effect.

**Symptom:** Custom annotation tau has very large SE, p-value > 0.5; baseline categories that were significant become non-significant.

**Fix:** Test annotations marginal to the baseline by including baseline-LD_v2.2 plus the new annotation only; never test multiple highly correlated annotations jointly; report VIF of annotation matrix; use the joint enrichment of {baseline + new} category not per-tau.

### HESS locus instability at sparse SNP density

**Trigger:** Running HESS at a locus with < 1000 LD-pruned SNPs (e.g. centromere-adjacent region).

**Mechanism:** HESS quadratic form on projected effect estimates is unstable at low SNP density; matrix conditioning explodes.

**Symptom:** Locus h2 estimate negative or > 0.5 (unphysical); standard error very large; subsequent loci stable.

**Fix:** Require >= 1000 SNPs per locus; use LDetect partition (Berisa & Pickrell 2016 Bioinformatics 32:283) which targets ~1700 loci genome-wide; discard sparse loci or merge with neighbors.

### Case-control LDSC observed vs liability scale

**Trigger:** Reporting LDSC h2 from a case-control GWAS on the observed (0/1) scale.

**Mechanism:** Observed-scale h2 depends on case fraction in the GWAS sample, not population prevalence; comparisons across studies require liability-scale transformation.

**Symptom:** h2 looks tiny (0.02) for a known-heritable disease; differs across studies with different case fractions.

**Fix:** Always supply `--samp-prev <case_fraction>` and `--pop-prev <population_lifetime_prevalence>` to LDSC; report h2 on liability scale. Without these flags, LDSC defaults to observed scale. Lee 2011 (AJHG 88:294) conversion: `h2_liab = h2_obs * (K(1-K))^2 / (P(1-P) * z^2)` (numerator is K^2(1-K)^2), where K = population prevalence, P = sample case proportion, z = standard-normal density at the quantile (1-K). LDSC applies this via `--samp-prev/--pop-prev`; verify K and P are assigned correctly (K is population, P is sample). Skipping the conversion typically yields a 2-10x underestimate vs the liability-scale truth.

## LDAK SumHer Pipeline

**Goal:** Alternative h2 and functional enrichment estimate using the LDAK-Thin model for reconciliation with LDSC.

**Approach:** Reformat sumstats to LDAK input -> run `ldak --sum-hers` against the pre-computed LDAK-Thin tagging file -> compare to LDSC.

```bash
# 1. LDAK requires header: Predictor A1 A2 n Z (Z optional; can use beta + se instead)
# Reference LDAK-Thin tagging files at dougspeed.com/pre-computed-tagging-files
ldak --sum-hers trait_sumher \
    --summary trait_ldak.txt \
    --tagfile ldak.thin.hapmap.gbr.tagging \
    --check-sums NO

# 2. Partitioned with BaselineLD annotations (two steps)
# BaselineLD provides binary + continuous annotations covering coding/conserved/regulatory/MAF
# bins; download BaselineLD.zip (96 annotations) from dougspeed.com/resources and extract to ./BaselineLD/BaselineLD{1..96} (the run uses the first 86).
# The annotation flags belong to --calc-tagging (which builds the tagging file), NOT to
# --sum-hers. LDAK uses --annotation-number + --annotation-prefix (continuous) or
# --partition-number + --partition-prefix (binary). No --category-file flag exists.

# 2a. Build the annotated tagging file from a genotype reference (--power -.25 = LDAK-Thin)
ldak --calc-tagging trait_bld --bfile ref_panel --power -.25 \
    --annotation-number 86 \
    --annotation-prefix BaselineLD/BaselineLD

# 2b. Estimate partitioned h2 against that tagging file (no annotation flags here)
ldak --sum-hers trait_bld --summary trait_ldak.txt \
    --tagfile trait_bld.tagging \
    --check-sums NO
```

Pre-computed tagging files exist for GBR (HapMap reference); other ancestries require building tagging file via `--calc-tagging`. LDAK SumHer outputs h2 estimate, per-category h2 share, and enrichment with Z-scores.

## HESS Local h2 Pipeline

**Goal:** Estimate per-locus heritability genome-wide using LDetect partition.

**Approach:** Step 1 computes quadratic forms per locus from LD reference; step 2 estimates h2; output per-locus h2 with SE.

```bash
# HESS step 1: per-chromosome local h2 quadratic forms (run per chromosome)
for chr in {1..22}; do
    hess.py \
        --local-hsqg trait.sumstats.gz \
        --chrom $chr \
        --bfile 1000G_EUR_chr${chr} \
        --partition LDetect_EUR_chr${chr}.bed \
        --out hess_chr${chr}
done

# HESS step 2: aggregate across chromosomes and estimate h2
hess.py \
    --prefix hess_chr \
    --out trait_local_h2 \
    --tot-hsqg <total_h2_estimate> <total_h2_SE>
# Provide total h2 and SE from LDSC for the global constraint
```

LDetect partition files (Berisa & Pickrell 2016) are available pre-computed for EUR/EAS/AFR at https://bitbucket.org/nygcresearch/ldetect-data. HESS detects high-h2 loci suitable for fine-mapping prioritization.

## HDL Genetic Correlation (R)

**Goal:** Genetic correlation with ~60% lower variance than LDSC when samples are non-overlapping.

**Approach:** Reformat sumstats to HDL input -> download UKB reference panel eigen-decomposition -> run HDL.rg.

```r
library(HDL)

# Sumstats need columns: SNP, A1, A2, b (beta), se, N
gwas1 <- read.table('trait1.txt', header = TRUE, stringsAsFactors = FALSE)
gwas2 <- read.table('trait2.txt', header = TRUE, stringsAsFactors = FALSE)

LD.path <- 'UKB_array_SVD_eigen90_extraction'

rg_result <- HDL.rg(gwas1.df = gwas1, gwas2.df = gwas2, LD.path = LD.path,
                    Nref = 335265, output.file = 'hdl_rg.log',
                    eigen.cut = 'automatic')

# rg_result: rg, rg.se, p, h2_1, h2_2, gen.cov
```

HDL UKB reference (`UKB_array_SVD_eigen90_extraction`) requires non-overlapping samples; if either GWAS is from UKB, HDL is biased.

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| LDSC h2 negative | Trait truly null heritable; or LD scores ancestry-mismatched | Verify mean chi-square > 1.02; switch to ancestry-matched LD; report as null |
| `munge_sumstats.py` drops > 50% of SNPs | Allele mismatch with HapMap3 SNPlist; or A1/A2 swapped | Inspect drop reasons; pre-harmonize alleles; check rsID format |
| LDSC intercept > 1.5 | Population stratification, cryptic relatedness, or extensive sample overlap | Report jointly with ratio; investigate per-cohort PC adjustment |
| Stratified LDSC enrichment > 100x | Tiny annotation (<0.1% genome) underpowered | Set annotation size floor >= 0.5%; report joint enrichment of larger composite category |
| LDAK h2 markedly different from LDSC h2 | Model assumption divergence (GCTA vs LDAK-Thin) | Per Gazal 2019 / Hou 2019; report both and flag model-dependence |
| HDL rg = NA or numerical error | Sumstat format wrong; or eigen.cut too aggressive | Use eigen.cut='automatic'; check column names exactly |
| HESS locus h2 negative | < 1000 SNPs in locus; LD ref-stat mismatch | Drop locus or merge with neighbor; ensure LD ref matches GWAS ancestry |
| `--samp-prev/--pop-prev` not supplied for case-control | LDSC defaults to observed scale | Always supply both for case-control; report liability-scale h2 |
| Cell-type S-LDSC: no tissue p < 2.5e-4 | Trait underpowered for tissue prioritization (mean chi-square low) | Pool with related traits via MTAG; or report no tissue distinguishable |
| LDAK tagging file: build mismatch | Using hg19 tagging on hg38 GWAS sumstats | Tagging files are build-specific; download matched build |
| BOLT-REML "matrix not positive definite" | GRM has duplicated individuals or extreme relatedness | Pre-filter to unrelated < 0.05 kinship; or use REML method-of-moments instead |
| `munge_sumstats.py`: missing N column | Per-SNP N column not supplied | Pass `--N <Ntot>` (numeric total) OR `--N-col N` (column name); pick one |
| `munge_sumstats.py`: all SNPs drop silently | A1/A2 flipped relative to HM3 reference (`--merge-alleles`) | Verify allele coding matches `w_hm3.snplist`; pre-harmonize or swap A1 <-> A2 |
| `munge_sumstats.py` drops multi-allelic SNPs | Expected behavior (LDSC requires biallelic) | Document the drop count in methods; not a fix |
| Sign of Z reversed across studies | `--signed-sumstats BETA,0` vs `--signed-sumstats Z,0` confusion | Use `BETA,0` for additive effect sign convention, `Z,0` for Z-score; never both; verify direction with a known sentinel SNP |

## Tool Install Notes

```bash
# LDSC Python 3 fork (official bulik/ldsc is Python 2.7, unmaintained since 2019)
# IMPORTANT: belowlab/ldsc v3.0.1 broke the --h2 / --rg / --h2-cts CLI per its README.
# For a working CLI matching the flags below, use abdenlab/ldsc-python3 (v2.0.0)
# OR run belowlab/ldsc via Docker: `docker pull jtb114/ldsc:latest`.
git clone https://github.com/abdenlab/ldsc-python3.git   # working CLI
cd ldsc-python3
pip install .   # abdenlab/ldsc-python3 is a Poetry project (pyproject.toml); no environment.yml/requirements.txt

# LDAK 6+
wget https://raw.githubusercontent.com/dougspeed/LDAK/main/ldak6.3.linux
chmod +x ldak6.3.linux

# Pre-computed reference resources (one-time download)
# EUR LD scores (HapMap3 SNPs)
wget https://alkesgroup.broadinstitute.org/LDSCORE/eur_w_ld_chr.tar.bz2
# Baseline-LD v2.2 (Gazal 2017)
wget https://alkesgroup.broadinstitute.org/LDSCORE/1000G_Phase3_baselineLD_v2.2_ldscores.tgz
# 1000G EUR frequency files
wget https://alkesgroup.broadinstitute.org/LDSCORE/1000G_Phase3_frq.tgz
# Weights
wget https://alkesgroup.broadinstitute.org/LDSCORE/1000G_Phase3_weights_hm3_no_MHC.tgz
# Multi-tissue chromatin ldcts (Finucane 2018)
wget https://alkesgroup.broadinstitute.org/LDSCORE/Multi_tissue_chromatin_1000Gv3_ldscores.tgz
```

```r
# HDL
remotes::install_github('zhenin/HDL/HDL')
# HDL UKB reference (downloads ~5 GB)
# https://github.com/zhenin/HDL/wiki/Reference-panels
```

```bash
# HESS (Python 2 by default; Python 3 fork: huwenboshi/hess Python 3 branch)
git clone https://github.com/huwenboshi/hess.git
pip install -r hess/requirements.txt

# BOLT-LMM / BOLT-REML
wget https://alkesgroup.broadinstitute.org/BOLT-LMM/downloads/BOLT-LMM_v2.4.1.tar.gz

# GCTA
wget https://yanglab.westlake.edu.cn/software/gcta/bin/gcta-1.94.1-linux-kernel-3-x86_64.zip

# Popcorn
git clone https://github.com/brielin/Popcorn.git && cd Popcorn && pip install .
```

## References

- Bulik-Sullivan BK et al 2015 Nat Genet 47:291 (LDSC)
- Bulik-Sullivan BK et al 2015 Nat Genet 47:1236 (cross-trait LDSC genetic correlation)
- Finucane HK et al 2015 Nat Genet 47:1228 (stratified LDSC baseline)
- Gazal S et al 2017 Nat Genet 49:1421 (baseline-LD model)
- Shi H & Gazal S et al 2021 Nat Commun 12:1098 (S-LDXR / baseline-LD-X cross-population)
- Finucane HK et al 2018 Nat Genet 50:621 (cell-type S-LDSC)
- Speed D et al 2017 Nat Genet 49:986-992 (LDAK model; cross-validation model comparison)
- Speed D, Holmes J & Balding DJ 2020 Nat Genet 52:458 (LDAK-Thin model; heritability model comparison)
- Speed D et al 2019 Nat Genet 51:277 (SumHer)
- Gazal S et al 2019 Nat Genet 51:1202-1204 (LDSC vs LDAK reconciliation, model-dependence)
- Hou K et al 2019 Nat Genet 51:1244 (heritability accuracy and h2 model comparison)
- Ning Z et al 2020 Nat Genet 52:859 (HDL)
- Shi H et al 2016 AJHG 99:139 (HESS univariate)
- Shi H et al 2017 AJHG 101:737 (HESS bivariate local rg)
- Loh PR et al 2015 Nat Genet 47:1385 (BOLT-REML)
- Yang J et al 2011 AJHG 88:76 (GCTA-GREML)
- Brown BC et al 2016 AJHG 99:76 (Popcorn trans-ancestry rg)
- Berisa T & Pickrell JK 2016 Bioinformatics 32:283 (LDetect locus partition)
- Li H, Kamath T, Mazumder R, Lin X, O'Connor LJ 2024 medRxiv 2024.11.04.24316716 (graphREML; published Nat Genet 2026)

## Related Skills

- causal-genomics/mendelian-randomization - h2 / rg-aware instrument selection and one-sample-equivalent design decisions
- causal-genomics/colocalization-analysis - Per-locus shared-causal evidence complementary to HESS local h2
- causal-genomics/fine-mapping - Credible-set construction at high-h2 HESS loci
- causal-genomics/pleiotropy-detection - Cross-trait pleiotropy via LCV / LHC-MR using LDSC outputs
- causal-genomics/genomic-sem - Genomic SEM extends LDSC rg to multivariate structural models
- causal-genomics/transcriptome-wide-association - TWAS uses partitioned-h2 weights for gene-level testing
- atac-seq/differential-accessibility - Per-cell-type chromatin annotations as S-LDSC input
- atac-seq/single-cell-atac - scATAC peaks per cluster as Finucane 2018 .ldcts annotations
- chip-seq/peak-calling - ENCODE / Roadmap chromatin marks for cell-type prioritization
- population-genetics/association-testing - GWAS source summary statistics for LDSC munging
- population-genetics/linkage-disequilibrium - LD reference panels for HESS / coloc.susie
- workflows/gwas-pipeline - Upstream GWAS pipeline feeding sumstats to LDSC

## Usage Guide

# Heritability Partitioning - Usage Guide

## Overview

Estimate SNP heritability (`h2_SNP`) and decompose it across functional categories, tissues, and individual loci using LD-score regression (LDSC), LDAK SumHer, HESS local h2, HDL high-definition likelihood, BOLT-REML, and GCTA-GREML. Choose between summary-statistic methods (LDSC, LDAK, HDL, HESS) and individual-level methods (BOLT-REML, GCTA), reconcile LDSC vs LDAK model-dependent enrichment estimates, prioritize trait-relevant cell types via Finucane 2018 chromatin partitioning, compute trans-ancestry rg with Popcorn, and report calibrated h2 with intercept and ratio diagnostics.

## Prerequisites

```bash
# Python 3 LDSC fork (official bulik/ldsc is Python 2.7 / unmaintained since 2019).
# belowlab/ldsc v3.0.1 broke the --h2/--rg/--h2-cts CLI per its README; for a
# working CLI use abdenlab/ldsc-python3 (v2.0.0) or run belowlab via Docker
# (`docker pull jtb114/ldsc:latest`).
git clone https://github.com/abdenlab/ldsc-python3.git
cd ldsc-python3 && pip install .   # Poetry project (pyproject.toml); no environment.yml

# LDAK 6+ (bare executable distributed via GitHub; no zip)
wget https://raw.githubusercontent.com/dougspeed/LDAK/main/ldak6.3.linux && chmod +x ldak6.3.linux

# Pre-computed reference resources (EUR; ~3-5 GB total one-time)
# All from https://alkesgroup.broadinstitute.org/LDSCORE/
#   eur_w_ld_chr.tar.bz2                           (univariate h2 / rg)
#   1000G_Phase3_baselineLD_v2.2_ldscores.tgz      (partitioned h2)
#   1000G_Phase3_frq.tgz                           (allele frequencies)
#   1000G_Phase3_weights_hm3_no_MHC.tgz            (regression weights)
#   Multi_tissue_chromatin_1000Gv3_ldscores.tgz    (Finucane 2018 cell-type prioritization)
```

```r
# HDL R package (genetic correlation with non-overlapping cohorts)
remotes::install_github('zhenin/HDL/HDL')
# Download HDL UKB SVD reference (~5 GB) per HDL wiki
```

Inputs: GWAS summary statistics with columns SNP, A1, A2, BETA (or Z), SE, P, N (per-SNP or column-supplied). Allele frequency column EAF strongly recommended. For case-control GWAS, also supply sample case fraction (`--samp-prev`) and population lifetime prevalence (`--pop-prev`).

## Quick Start

Tell your AI agent what you want to do:
- "Compute SNP heritability from this GWAS summary statistic file with LDSC, EUR ancestry"
- "Partition h2 across functional annotations using the baseline-LD v2.2 model"
- "Prioritize trait-relevant tissues from ENCODE chromatin marks via Finucane 2018 cell-type S-LDSC"
- "Compute genetic correlation between trait1 and trait2 from sumstats; use cross-trait LDSC because samples overlap"
- "Run HDL.rg for genetic correlation since cohorts are non-overlapping; want lower variance than LDSC"
- "Compute local heritability per LDetect locus with HESS and identify high-h2 loci for fine-mapping"
- "Reconcile LDSC and LDAK SumHer enrichment estimates for the conserved-region annotation"
- "Convert this case-control LDSC h2 from observed to liability scale; population prevalence is 0.005"
- "Run Popcorn for trans-ancestry rg between this EUR GWAS and the matched EAS GWAS"

## Example Prompts

### Total h2 from EUR Sumstats
> "Munge `gwas_T2D.tsv` with LDSC's `munge_sumstats.py` against the HapMap3 SNP list, then run `ldsc.py --h2` with `eur_w_ld_chr/` for the univariate estimate. Report intercept, mean chi-square, ratio, and h2 with SE on the liability scale (samp-prev 0.08, pop-prev 0.10)."

### Partitioned h2 with Baseline-LD
> "Partition T2D h2 across the baseline-LD v2.2 annotations. Use `--overlap-annot --print-coefficients`. Apply Bonferroni at `0.05 / N_annotations` for per-annotation enrichment claims. Report the top 5 categories with enrichment > 5x and joint p < 2e-3."

### Cell-Type / Tissue Prioritization (Finucane 2018)
> "Prioritize trait-relevant tissues using the Multi_tissue_chromatin_1000Gv3 ldcts file with `ldsc.py --h2-cts`. Apply Bonferroni at `0.05 / N_tissue` (~ 2.5e-4 for 200 tissues). Cross-reference top tissues against the disease's known biology."

### LDSC vs LDAK Reconciliation
> "Functional enrichment claim depends on the per-SNP heritability model. Run BOTH LDSC baseline-LD AND LDAK SumHer with LDAK-Thin tagging. If they disagree by > 2x, report enrichment as model-dependent (the unresolved S-LDSC vs LDAK enrichment debate: Gazal 2019 Nat Genet 51:1202 favours baseline-LD S-LDSC; the LDAK developers defend SumHer, Speed 2020 Nat Genet 52:458). Prefer LDAK for conserved regions per Speed 2019."

### Cross-Trait Genetic Correlation
> "Estimate rg between trait1 and trait2 from sumstats. If sample overlap > 5%, use cross-trait LDSC (`ldsc.py --rg`) because HDL is biased under overlap. If non-overlapping, use HDL for ~60% lower variance. Report rg, SE, p, and cross-trait intercept."

### Local Heritability
> "Compute per-locus h2 across all 22 autosomes using HESS with the LDetect EUR partition (Berisa & Pickrell 2016). Require each locus to have >= 1000 SNPs. Identify loci with h2 > 0.001 for fine-mapping prioritization downstream."

### Liability-Scale Case-Control h2
> "Case-control GWAS for schizophrenia. Supply `--samp-prev <case_fraction>` and `--pop-prev 0.01` so LDSC reports h2 on the liability scale. Without these flags, observed-scale h2 is incomparable across studies."

### Non-EUR Ancestry h2
> "EAS GWAS for type 2 diabetes. Use ancestry-matched LD scores from the EAS folder on alkesgroup.broadinstitute.org/LDSCORE, NOT the default EUR scores. Mismatched LD biases h2 downward and inflates the intercept."

### Trans-Ancestry rg
> "Cross-population genetic correlation between EUR and EAS GWAS for the same trait. Use Popcorn with per-population LD scores. Require effective N > 5000 per population for stable estimation."

### Single-Cell ATAC Annotation
> "Build cell-type-specific .ldcts from per-cluster ATAC peaks (cross-reference atac-seq/single-cell-atac). Compute per-cluster LD scores via `ldsc.py --l2`. Then run `--h2-cts` to identify which cluster's open-chromatin landscape is most heritability-enriched for the trait."

## What the Agent Will Do

1. Munge sumstats to LDSC format with HapMap3 SNP filter (`munge_sumstats.py`)
2. Compute total h2 with `--h2` and report intercept, mean chi-square, ratio jointly
3. Apply liability-scale conversion for case-control with `--samp-prev` and `--pop-prev`
4. Run baseline-LD v2.2 partitioned h2 with `--overlap-annot --print-coefficients`
5. Run Finucane 2018 cell-type S-LDSC with `--h2-cts` and Bonferroni-control per-tissue p
6. For trait pairs, decide cross-trait LDSC (overlap-tolerant) vs HDL (lower variance, no overlap)
7. Run LDAK SumHer as model-reconciliation alongside LDSC when enrichment claim is primary
8. For local h2, run HESS per chromosome with LDetect partition, aggregate genome-wide
9. For individual-level data, route to BOLT-REML (N > 100k) or GCTA-GREML (5k < N < 50k)
10. Report intercept, mean chi-square, ratio, h2 with SE, partitioned enrichment, and sensitivity over model

## Method Selection Quick Reference

| Have | N | Goal | Method |
|------|---|------|--------|
| Sumstats (EUR) | >= 50k | Total h2 | LDSC `--h2` |
| Sumstats (EUR) | >= 50k | Partitioned h2 | S-LDSC + baseline-LD v2.2 |
| Sumstats (EUR) | >= 50k | Tissue prioritization | S-LDSC `--h2-cts` (Finucane 2018) |
| Sumstats (EUR) | >= 50k each | rg, non-overlap | HDL |
| Sumstats (EUR) | >= 50k each | rg, overlap unknown | Cross-trait LDSC |
| Sumstats (non-EUR) | >= 50k | Total h2 | LDSC with ancestry-matched LD |
| Sumstats (multi-pop) | >= 5k per pop | Trans-ancestry rg | Popcorn |
| Sumstats (EUR) | varies | Local h2 | HESS with LDetect partition |
| Individual genotypes | 5k - 50k | h2 | GCTA-GREML |
| Individual genotypes | > 100k | h2 multi-component | BOLT-REML |
| Two models matter | -- | Functional enrichment | LDSC + LDAK SumHer (report both) |

## Cell-Type / Tissue Prioritization Workflow

Finucane 2018 cell-type S-LDSC asks: which tissue's chromatin annotation contributes most to trait h2 conditional on the baseline-LD model?

1. Download `Multi_tissue_chromatin_1000Gv3_ldscores.tgz` from alkesgroup (covers Roadmap, ENCODE, GTEx)
2. Manifest `.ldcts` file lists one row per tissue: `<name> <ldscore_prefix>,<control_ldscore_prefix>`
3. `ldsc.py --h2-cts trait.sumstats.gz --ref-ld-chr-cts <manifest>.ldcts --ref-ld-chr baseline. --w-ld-chr weights.`
4. Output `*.cell_type_results.txt` has per-tissue Coefficient, SE, p-value
5. Apply Bonferroni at `0.05 / N_tissues` (~2.5e-4 for 200 tissues)
6. Top trait-relevant tissues = those passing Bonferroni AND with positive coefficient

For novel cell types (e.g. per-cluster scATAC), build a custom .ldcts by computing per-cluster LD scores from chromatin BED files via `ldsc.py --l2 --bfile <ref> --annot <cluster>.annot.gz --thin-annot --out <cluster>`.

## LDSC vs LDAK Decision Matrix

| Claim | Use | Confirm with |
|-------|-----|--------------|
| Total h2 (no enrichment) | LDSC | LDAK only if intercept anomalous |
| Functional enrichment (primary claim) | LDSC + LDAK SumHer | Report both; flag model-dependence if discordant (Gazal 2019) |
| Cell-type prioritization | LDSC `--h2-cts` (Finucane 2018) | Optional: LDAK conditional on annotation |
| Conserved-region enrichment | LDAK SumHer (Speed 2019 recommends) | LDSC as comparison |
| Total rg, non-overlap | HDL primary | Cross-trait LDSC confirmatory |
| Total rg, with overlap | Cross-trait LDSC | -- |

## Computational Footprint

| Method | Per-trait runtime | Hardware |
|--------|------------------|----------|
| LDSC h2 (univariate) | minutes | laptop |
| Stratified LDSC + baseline-LD | 10-20 min | laptop |
| LDSC cell-type prioritization (~200 tissues) | hours, single-threaded | server |
| HESS genome-wide local h2 | hours per chromosome | cluster |
| BOLT-REML at N = 500k | days | cluster |
| HDL.rg (genetic correlation) | seconds to minutes | laptop |
| LDAK SumHer | tens of minutes | laptop |

graphREML on biobank-scale (N > 200k) typically beats S-LDSC per-trait runtime when an LDGM panel is available. Build runtime escalates with annotation count; cell-type prioritization with ~200 tissues is the most expensive per-trait step.

## Intercept Diagnostic Quick Reference

| Intercept | Ratio | Interpretation |
|-----------|-------|----------------|
| ~1.0 | ~0 | No inflation; h2 trustworthy |
| 1.0 - 1.1 | < 0.2 | Mostly polygenic; h2 trustworthy |
| 1.1 - 1.3 | 0.2 - 0.5 | Mild inflation; investigate population structure / sample overlap |
| 1.3 - 1.5 | 0.5 - 0.8 | Substantial inflation; report ratio jointly; consider re-genotype-QC |
| > 1.5 | -- | Re-run after PC adjustment or genomic control; do not interpret h2 |

## Tips

- LDSC intercept > 1 is NOT automatic evidence of confounding; report the ratio statistic jointly with mean chi-square.
- LDAK SumHer and LDSC use different per-SNP heritability priors; report both when enrichment is the primary claim (S-LDSC vs LDAK enrichment debate; Gazal 2019 Nat Genet 51:1202).
- HDL is biased when sample overlap > 5%; use cross-trait LDSC instead under any suspected overlap.
- Apply ancestry-matched LD scores for non-EUR GWAS; EUR scores on EAS / AFR sumstats yield biased h2 and inflated intercept.
- Always supply `--samp-prev` and `--pop-prev` for case-control GWAS; observed-scale h2 is not comparable across studies.
- For Finucane 2018 cell-type prioritization, Bonferroni at `0.05 / N_tissues` (~2.5e-4 for 200 tissues); report top tissues only if they pass.
- HESS requires >= 1000 SNPs per locus and an ancestry-matched LD reference; use the LDetect partition (Berisa & Pickrell 2016).
- For individual-level data with N > 100k, BOLT-REML is more precise than LDSC; for N 5k - 50k use GCTA-GREML.
- LDSC's official `bulik/ldsc` repository is Python 2.7 and unmaintained since 2019. Prefer `abdenlab/ldsc-python3` (v2.0.0) for the Python 3 CLI; the `belowlab/ldsc` v3.0.1 README states the `--h2 / --rg / --h2-cts` CLI is currently broken (Docker `jtb114/ldsc:latest` is the recommended belowlab-flavored fallback).
- Reference baseline-LD model: `baselineLD_v2.2` (Gazal 2017). Older `baselineLD_v1.1` and pre-baseline-LD `baseline_v1.1` exist but are superseded.
- Pre-compute LD scores once and reuse; downloading the EUR reference is ~3 GB but covers all standard LDSC analyses.

## Related Skills

causal-genomics/mendelian-randomization - h2 / rg-aware instrument selection and sample-overlap decisions
causal-genomics/colocalization-analysis - Per-locus shared-causal evidence complementary to HESS local h2
causal-genomics/fine-mapping - Credible-set construction at high-h2 HESS loci
causal-genomics/pleiotropy-detection - Cross-trait pleiotropy via LCV / LHC-MR using LDSC outputs
causal-genomics/genomic-sem - Genomic SEM extends LDSC rg to multivariate structural models
causal-genomics/transcriptome-wide-association - TWAS uses partitioned-h2 weights for gene-level testing
atac-seq/differential-accessibility - Per-cell-type chromatin annotations as S-LDSC input
atac-seq/single-cell-atac - scATAC peaks per cluster as .ldcts annotations
chip-seq/peak-calling - ENCODE / Roadmap chromatin marks for cell-type prioritization
population-genetics/association-testing - GWAS source summary statistics for LDSC munging
population-genetics/linkage-disequilibrium - LD reference panels for HESS / coloc.susie
workflows/gwas-pipeline - Upstream GWAS pipeline feeding sumstats to LDSC

## Bundled Files

- `causal-genomics--heritability-partitioning--examples--ldak_sumher.sh` — copied from `examples/ldak_sumher.sh`
- `causal-genomics--heritability-partitioning--examples--ldsc_partitioned_h2.sh` — copied from `examples/ldsc_partitioned_h2.sh`
