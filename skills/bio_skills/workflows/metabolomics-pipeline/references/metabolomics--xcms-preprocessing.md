# bio-metabolomics-xcms-preprocessing

> Bundled component reference for `metabolomics/xcms-preprocessing` (original source: `skills/bio_skills/metabolomics/xcms-preprocessing`).

Programmatic untargeted LC-MS feature extraction in R with the modern xcms 4.x MsExperiment/XcmsExperiment API, taking raw mzML to a feature table via CentWave peak detection, retention-time alignment, peak-density correspondence, gap-filling, CAMERA redundancy collapse, and built-in QC feature filtering. Use when converting centroided LC-MS runs into a features-by-samples matrix and deciding centWave/grouping/alignment parameters. For drift correction and QC/CV filtering execution see metabolomics/normalization-qc; for metabolite identification see metabolomics/metabolite-annotation; for the MS-DIAL GUI alternative with MS2Dec deconvolution see metabolomics/msdial-preprocessing; for downstream statistics see metabolomics/statistical-analysis.

## Instructions

## Version Compatibility

Reference examples tested with: xcms 4.x+ (MsExperiment/XcmsExperiment containers), Spectra 1.12+, CAMERA 1.58+

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('xcms')` then `?CentWaveParam` to verify parameter names and defaults

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

A feature table is only meaningful alongside its full processing specification: which xcms version, every `*Param` value, and the fill/filter ordering. The table is a parameterized hypothesis about which molecules exist, not the data.

# XCMS Untargeted LC-MS Preprocessing

**"Turn my raw LC-MS files into a feature table"** -> Detect chromatographic peaks per file, align retention times across runs, group corresponding peaks into features, fill gaps, then collapse adduct/isotope redundancy.
- R: `readMsExperiment()` -> `findChromPeaks()` -> `adjustRtime()` -> `groupChromPeaks()` -> `fillChromPeaks()` (xcms)

## The Single Most Important Insight -- The Feature Table Is a Model-Dependent Artifact, Not Ground Truth

Every cell in the table is the output of a detection + grouping + filling model with chosen parameters. Two analysts with different centWave/grouping settings produce materially different tables from identical raw files, so "not detected" is a statement about the parameters, not the sample. Three consequences reorganize the whole workflow: (1) preprocessing parameters silently set the detection floor - a compound absent from results may be present in the raw data but excluded by `noise`/`prefilter`/`peakwidth`/`snthresh`; (2) `fillChromPeaks` integrates whatever signal sits in a feature window even when no peak exists, fabricating a positive number where the honest answer is "below detection"; (3) one compound yields 5-15 features (adducts, isotopologues, in-source fragments, multimers), so a 10,000-feature table is plausibly ~1,000 compounds (Mahieu 2017). Report parameters as part of the result, inspect EICs and alignment of every hit, and collapse redundancy before annotation.

## API Generations -- Use Modern, Not Legacy

| Path | Containers | Verbs | Status |
|------|-----------|-------|--------|
| Modern (xcms 4.x) | `MsExperiment` (raw, Spectra backend) / `XcmsExperiment` (result) | `findChromPeaks` / `adjustRtime` / `groupChromPeaks` / `fillChromPeaks` driven by `*Param` objects | Preferred |
| Legacy (xcms <3) | `xcmsSet` / `xcmsRaw` | `findPeaks` / `group` / `retcor` / `fillPeaks`; `readMSData(mode='onDisk')` | Deprecated - do not use in new code |

Parameters are objects, not loose args: `findChromPeaks(data, param = CentWaveParam(...))`, never `findChromPeaks(data, ppm=..., peakwidth=...)`.

## Decision Tree by Scenario

| Situation | Do | Why |
|-----------|----|----|
| High-res centroid (Orbitrap, Q-Exactive, qTOF) | `CentWaveParam` | Wavelet on real mass traces, no fixed binning |
| Low-res / quadrupole / profile-only | `MatchedFilterParam` | Model-peak on binned EICs tolerates poor resolution |
| Profile data of any kind | Centroid first (msconvert vendor peakPicking, or `Spectra::pickPeaks`) | centWave requires centroids; profile input yields garbage mass traces |
| Many shared, well-behaved peaks across samples | `PeakGroupsParam` (after an initial `groupChromPeaks`) | Loess on universal anchor peaks; gentle and fast |
| Few shared peaks / sparse / strong nonlinear drift | `ObiwarpParam` | Full-profile warping needs no prior peaks |
| Cohort with large case/control compositional differences | `ObiwarpParam`, or `PeakGroupsParam` with `subset =` QC indices | Few universal anchors mis-register the condition-specific metabolome |
| New instrument, no parameter priors | AutoTuner / IPO for a starting neighborhood, then verify against EIC FWHM | Optimizers maximize a surrogate, not biology (McLean 2020) |
| GC-EI data | Deconvolution tools, not xcms peak picking -> metabolomics/msdial-preprocessing | Co-elution + universal fragmentation require component separation first |

## Peak Detection

**Goal:** Detect chromatographic peaks in each centroided file.

**Approach:** Build a `CentWaveParam` with `ppm` and `peakwidth` set from the actual instrument and chromatography (see Quantitative Thresholds), then call `findChromPeaks`.

```r
library(xcms)
# spectraFiles: centroided mzML paths; pd: data.frame with one row per file
raw <- readMsExperiment(spectraFiles = mzml_files, sampleData = pd)

# ppm is across-scan centroid scatter (~2-3x measured error), NOT the spec mass accuracy.
# peakwidth is c(min, max) in SECONDS, measured from EIC base-widths of known peaks.
cwp <- CentWaveParam(ppm = 10, peakwidth = c(2, 20), snthresh = 10,
                     prefilter = c(3, 1000), noise = 1000, mzdiff = -0.001,
                     integrate = 1L, mzCenterFun = 'wMean')
xdata <- findChromPeaks(raw, param = cwp)
nrow(chromPeaks(xdata))
```

## Retention-Time Alignment

**Goal:** Remove cross-run RT drift so the same compound lands at the same RT in every sample.

**Approach:** Choose obiwarp (no prior peaks) or peakGroups (anchor-based); align to a pooled QC, never to file #1. Regroup afterward because RTs changed.

```r
# obiwarp: full-profile warping. binSize here is the m/z profile bin (default 1),
# distinct from PeakDensityParam$binSize and MatchedFilterParam$binSize.
xdata <- adjustRtime(xdata, param = ObiwarpParam(binSize = 0.6))

# peakGroups alternative needs an initial correspondence and good universal anchors:
# xdata <- groupChromPeaks(xdata, param = pdp_anchor)
# xdata <- adjustRtime(xdata, param = PeakGroupsParam(minFraction = 0.85, span = 0.4,
#     subset = which(sampleData(xdata)$sample_type == 'QC'), subsetAdjust = 'average'))
plotAdjustedRtime(xdata)
```

## Correspondence (Grouping)

**Goal:** Match peaks across samples into consensus features.

**Approach:** Peak-density grouping in m/z slices; `bw` is the dominant knob and must reflect residual post-alignment RT scatter, not raw peak width.

```r
pdp <- PeakDensityParam(sampleGroups = sampleData(xdata)$sample_group,
                        bw = 5, minFraction = 0.5, minSamples = 1, binSize = 0.025)
xdata <- groupChromPeaks(xdata, param = pdp)
nrow(featureDefinitions(xdata))
```

## Gap-Filling

**Goal:** Integrate signal for features missing a detected peak in some samples.

**Approach:** `fillChromPeaks` with `ChromPeakAreaParam`; treat filled values as imputations, not measurements.

```r
xdata <- fillChromPeaks(xdata, param = ChromPeakAreaParam())
filled <- chromPeakData(xdata)$is_filled   # logical flag; lives in chromPeakData, not chromPeaks
feat <- featureValues(xdata, value = 'into')        # features x samples matrix
defs <- featureDefinitions(xdata)                   # mzmed / rtmed / npeaks per feature
```

## Redundancy Collapse

**Goal:** Group the same compound's adducts/isotopes/fragments back toward compound spectra before annotation.

**Approach:** CAMERA in order groupFWHM -> groupCorr -> findIsotopes -> findAdducts (isotopes before adducts). Correlation grouping needs enough samples to be meaningful and can over- or under-merge - verify against the table size.

```r
library(CAMERA)
xsa <- xsAnnotate(as(xdata, 'xcmsSet'))
xsa <- groupFWHM(xsa, perfwhm = 0.6)
xsa <- groupCorr(xsa)
xsa <- findIsotopes(xsa, mzabs = 0.01, ppm = 10)
xsa <- findAdducts(xsa, polarity = 'positive')
peaklist <- getPeaklist(xsa)
```

## QC Feature Filtering (Preprocessing/QC Bridge)

**Goal:** Drop features that fail conventional QC, operationalizing Broadhurst 2018 inside the xcms object.

**Approach:** `filterFeatures` with `RsdFilter` (CV in QCs), `DratioFilter` (sd_QC/sd_sample), `PercentMissingFilter`, `BlankFlag`. Drift correction and the full QC pipeline live in metabolomics/normalization-qc.

```r
qc <- sampleData(xdata)$sample_group == 'QC'
study <- sampleData(xdata)$sample_group %in% c('Control', 'Treatment')
xdata <- filterFeatures(xdata, filter = RsdFilter(threshold = 0.3, qcIndex = qc))
xdata <- filterFeatures(xdata, filter = DratioFilter(threshold = 0.5, qcIndex = qc, studyIndex = study))
```

## Per-Method Failure Modes

### ppm set to the spec sheet
- **Trigger:** Setting `ppm = 3` because the Orbitrap datasheet says 3 ppm.
- **Mechanism:** centWave `ppm` is across-scan centroid scatter, which exceeds time-averaged mass accuracy; too tight fragments one ion into short ROIs that each fail `prefilter`.
- **Symptom:** Features vanish entirely (not degrade); the better the instrument spec, the worse it looks.
- **Fix:** Set `ppm` to ~2-3x the empirical per-scan centroid scatter, not the datasheet number.

### peakwidth mismatch
- **Trigger:** Copying the default `c(20, 50)` onto modern UHPLC.
- **Mechanism:** Lower bound too high discards sharp 2-5 s peaks; upper bound too low clips broad HILIC/tailing peaks. No warning is emitted.
- **Symptom:** Real peaks silently absent from the table.
- **Fix:** Measure base-width FWHM from 5-10 known EICs; set `peakwidth ~ c(0.5x min, 2x max)`.

### prefilter/noise/snthresh as the trace guillotine
- **Trigger:** Tuning `snthresh` while `prefilter[I]` already kills the trace.
- **Mechanism:** These are three serial gates on the same low-intensity signal; the lowest wins. On high-baseline instruments the default `I=100` may both under-filter noise and kill trace metabolites.
- **Symptom:** Trace metabolites never appear regardless of `snthresh`.
- **Fix:** Lower `prefilter[I]` first for trace work; the lowest gate dominates.

### bw too coarse / alignment-coupled
- **Trigger:** Copying `bw = 30` onto UHPLC, or choosing `bw` independently of alignment quality.
- **Mechanism:** On UHPLC, `bw=30` merges chromatographically resolved co-eluting compounds; with poor alignment a tight `bw` instead splits one compound across features.
- **Symptom:** Averaged-away differences (over-merge) or duplicate split features (under-merge).
- **Fix:** Set `bw` from residual post-alignment RT scatter (often 2-6 s on UHPLC); inspect EICs of merged/split features.

### gap-filling fabricates intensities
- **Trigger:** Feeding a naively filled table straight into a t-test.
- **Mechanism:** Missingness is MNAR (below LOD); filling integrates the noise floor into a positive number, inflating the absent group's mean and shrinking the fold-change being tested.
- **Symptom:** "Significant" features that are mostly filled in one group.
- **Fix:** Track `is_filled`; report per-feature filled fraction; for inference use unfilled values with MNAR-aware imputation (QRILC/GSimp), reserving the fill for dense exploratory PCA.

### skipping redundancy collapse
- **Trigger:** Treating feature count as compound count.
- **Mechanism:** One compound makes 5-15 features (~90% of features are degenerate, Mahieu 2017); correlated adduct "hits" multiply the multiple-testing burden.
- **Symptom:** Inflated dimensionality; clusters of co-significant features that are one molecule.
- **Fix:** Run CAMERA/RAMClustR before annotation; treat collapse as a tunable false-merge/false-split tradeoff with no ground truth.

## Quantitative Thresholds

| Threshold | Source | Rationale |
|-----------|--------|-----------|
| `ppm` Orbitrap/Q-Exactive 5-10, qTOF 15-30 | Tautenhahn 2008; instrument physics | ~2-3x measured across-scan centroid scatter, not spec accuracy |
| `peakwidth` UHPLC c(2,20), HPLC c(10,40), HILIC c(10,60) (s) | Smith 2006; chromatography | Must bracket measured EIC base-widths; default c(20,50) wrong for UHPLC |
| Points across peak >= ~6-7 | Zeng 2023 *JASMS* 34:1136 | Below this, peak-area precision degrades non-linearly; an acquisition limit no parameter recovers |
| `prefilter = c(3, I)` | Tautenhahn 2008 | Min 3 consecutive scans above intensity I; I set per instrument baseline |
| Grouping `bw` 2-6 s (UHPLC) | xcms vignette | Default 30 s merges resolved co-eluting compounds on fast chromatography |
| QC CV (RSD) < 0.20-0.30 | Broadhurst 2018 *Metabolomics* 14:72 | Features with high QC variance are unreliable |
| D-ratio < 0.5 | Broadhurst 2018 | Technical variance must sit well below biological |
| Blank flag k ~ 3-5 | Broadhurst 2018 | Test-sample mean must exceed k x blank mean |
| ~1 compound per 5-15 features | Mahieu 2017 *Anal Chem* 89:10397 | ~90% of detected features are adduct/isotope/fragment degeneracy |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| `could not find function "readMSData"` or legacy verbs missing | Using deprecated `xcmsSet`/`readMSData` API on xcms 4.x | Use `readMsExperiment()` + the `findChromPeaks`/`groupChromPeaks` verbs |
| `unused argument (ppm = ...)` in findChromPeaks | Passing loose args instead of a `*Param` object | Wrap in `CentWaveParam(...)` and pass via `param =` |
| Features defined on uncorrected RT | Skipped the regroup after `adjustRtime` | Call `groupChromPeaks` again after alignment |
| Garbage mass traces, almost no peaks | Profile (non-centroid) data fed to centWave | Centroid first (msconvert vendor peakPicking or `Spectra::pickPeaks`) |
| `sampleGroups` length/semantics error | Vector misaligned with sample order or missing | Pass `sampleData(xdata)$group` matching file order; it is mandatory |
| Three different `binSize` defaults confused | obiwarp (m/z, default 1) vs PeakDensity (m/z, 0.25) vs matchedFilter (m/z, 0.1) | Set each in its own `*Param`; they are not the same knob |
| `as(xdata, 'xcmsSet')` fails or warns | CAMERA expects the legacy container | Coerce the `XcmsExperiment` to `xcmsSet` only for CAMERA; keep modern objects upstream |

## References

- Smith CA, Want EJ, O'Maille G, Abagyan R, Siuzdak G. 2006. XCMS: processing mass spectrometry data for metabolite profiling using nonlinear peak alignment, matching, and identification. *Anal Chem* 78:779-787.
- Tautenhahn R, Bottcher C, Neumann S. 2008. Highly sensitive feature detection for high resolution LC/MS (centWave). *BMC Bioinformatics* 9:504.
- Prince JT, Marcotte EM. 2006. Chromatographic alignment of ESI-LC-MS proteomic data sets by ordered bijective interpolated warping. *Anal Chem* 78:6140-6152.
- Lange E, Tautenhahn R, Neumann S, Gropl C. 2008. Critical assessment of alignment procedures for LC-MS proteomics and metabolomics measurements. *BMC Bioinformatics* 9:375.
- Kuhl C, Tautenhahn R, Bottcher C, Larson TR, Neumann S. 2012. CAMERA: an integrated strategy for compound spectra extraction and annotation of LC/MS data sets. *Anal Chem* 84:283-289.
- Myers OD, Sumner SJ, Li S, Barnes S, Du X. 2017. Detailed investigation and comparison of the XCMS and MZmine 2 chromatogram construction and chromatographic peak detection methods. *Anal Chem* 89:8689-8695.
- Mahieu NG, Patti GJ. 2017. Systems-level annotation of a metabolomics data set reduces 25,000 features to fewer than 1,000 unique metabolites. *Anal Chem* 89:10397-10406.
- McLean CM, Kujawinski EB. 2020. AutoTuner: high fidelity and robust parameter selection for metabolomics data processing. *Anal Chem* 92:5724-5732.
- Broadhurst D, Goodacre R, Reinke SN, Kuligowski J, Wilson ID, Lewis MR, Dunn WB. 2018. Guidelines and considerations for the use of system suitability and quality control samples in mass spectrometry assays applied in untargeted clinical metabolomic studies. *Metabolomics* 14:72.
- Zeng W, Bateman KP. 2023. Quantitative LC-MS/MS. 1. Impact of points across a peak on the accuracy and precision of peak area measurements. *J Am Soc Mass Spectrom* 34(6):1136-1144.
- Louail P, Brunius C, Garcia-Aloy M, et al. 2025. xcms in peak form: now anchoring a complete metabolomics data preprocessing and analysis software ecosystem. *Anal Chem* 97:27639-27645.

## Related Skills

- metabolomics/normalization-qc - Drift correction, CV/D-ratio filtering, and feature-table normalization
- metabolomics/metabolite-annotation - Identification of features into named metabolites
- metabolomics/msdial-preprocessing - GUI/MS-DIAL alternative with MS2Dec deconvolution and GC-EI support
- metabolomics/statistical-analysis - Differential and multivariate statistics on the feature table

## Usage Guide

# XCMS Untargeted LC-MS Preprocessing Usage Guide

## Overview

This skill drives programmatic untargeted LC-MS feature extraction in R with the modern xcms 4.x API: raw centroided mzML in, a features-by-samples intensity table out, via CentWave peak detection, retention-time alignment, peak-density correspondence, gap-filling, CAMERA redundancy collapse, and built-in QC feature filtering. It guards against the traps that make untargeted tables untrustworthy: parameters that silently delete real peaks, gap-filling that fabricates intensities for absent compounds, alignment that looks perfect in QCs while mis-registering rare features, and the one-compound-many-features redundancy that inflates apparent dimensionality.

## Prerequisites

```r
if (!require('BiocManager')) install.packages('BiocManager')
BiocManager::install(c('xcms', 'MsExperiment', 'Spectra', 'CAMERA'))
```

Conceptual prerequisites: data must be centroided (centroid in software with a documented algorithm, e.g. ProteoWizard msconvert vendor peakPicking, rather than relying on irreversible on-instrument centroiding); the instrument class and chromatography must be known to set `ppm` and `peakwidth`; the sample design (biological groups, pooled QCs, blanks, injection order) must be recorded as a per-file table before processing; and the analyst should understand that the resulting feature table is a parameterized result that must be reported with its full processing specification.

## Quick Start

Tell your AI agent what you want to do:
- "Process my centroided mzML files with xcms into a feature table"
- "Detect peaks with CentWave using parameters appropriate for my Orbitrap UHPLC data"
- "Align retention times with obiwarp and group peaks across samples"
- "Gap-fill, then report the fraction of filled values per feature"
- "Collapse adduct and isotope redundancy with CAMERA before annotation"
- "Filter features by QC CV and D-ratio with xcms filterFeatures"

## Example Prompts

### Peak Detection
> "Set up CentWaveParam for qTOF UHPLC data and explain why ppm should not be the spec mass accuracy."
> "My trace metabolites are missing from the table - which of prefilter, noise, and snthresh should I lower first?"

### Alignment and Grouping
> "Align retention times to a pooled QC reference rather than the first file, then regroup."
> "Choose between obiwarp and peakGroups for a heterogeneous case/control cohort with few shared peaks."
> "Set the grouping bw relative to my residual post-alignment RT scatter on UHPLC."

### Gap-Filling and QC
> "Gap-fill with ChromPeakAreaParam but flag the filled values and report per-feature filled fraction."
> "Filter features with RsdFilter and DratioFilter using my QC and study sample indices."

### Redundancy and Export
> "Run CAMERA in the correct order to collapse adducts and isotopes before annotation."
> "Export the feature table with mz, rt, and intensities for downstream statistics."

## What the Agent Will Do

1. Load centroided mzML into an `MsExperiment` via `readMsExperiment` with a per-file sample table.
2. Run `findChromPeaks` with a `CentWaveParam` (or `MatchedFilterParam` for low-res/profile data) tuned to the instrument and chromatography.
3. Align retention times with `ObiwarpParam` or `PeakGroupsParam`, then regroup.
4. Group peaks into features with `PeakDensityParam`.
5. Gap-fill with `ChromPeakAreaParam`, tracking `is_filled`.
6. Collapse redundancy with CAMERA and optionally filter features with `filterFeatures`.
7. Export the features-by-samples matrix with mz/rt annotations and the full parameter set.

## Tips

- Use CentWave for centroided high-res data (most modern instruments); MatchedFilter only for low-res/quadrupole/profile data.
- Measure `peakwidth` from real EIC base-widths; the default c(20,50) silently drops sharp UHPLC peaks.
- Set `ppm` from empirical across-scan centroid scatter (~2-3x), not the datasheet - too tight fragments mass traces and deletes features.
- Align to a pooled QC or representative mid-batch run; aligning to file #1 propagates an outlier's idiosyncrasy into every warp.
- Inspect RT-deviation plots and a few EICs of significant features; alignment can look perfect in QCs while corrupting rare features.
- Treat filled values as imputations: track `is_filled`, report filled fractions, and prefer MNAR-aware imputation for inferential statistics.
- A finding that survives only one software/parameter set is a candidate, not a result; report the full processing specification.

## Related Skills

- metabolomics/normalization-qc - Drift correction, CV/D-ratio filtering, and feature-table normalization
- metabolomics/metabolite-annotation - Identification of features into named metabolites
- metabolomics/msdial-preprocessing - GUI/MS-DIAL alternative with MS2Dec deconvolution and GC-EI support
- metabolomics/statistical-analysis - Differential and multivariate statistics on the feature table

## Bundled Files

- `metabolomics--xcms-preprocessing--examples--xcms_workflow.R` — copied from `examples/xcms_workflow.R`
