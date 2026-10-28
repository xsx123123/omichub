# bio-flow-cytometry-cytometry-qc

> Bundled component reference for `flow-cytometry/cytometry-qc` (original source: `skills/bio_skills/flow-cytometry/cytometry-qc`).

Quality control for flow, spectral, and mass cytometry - time-based anomaly cleaning (flowAI, flowCut, PeacoQC, flowClean), margin/boundary event removal, signal-drift detection, dead-cell exclusion, CyTOF Gaussian/DNA/event-length checks, instrument calibration/standardization (MESF, CS&T, peak-2), and batch-level outlier flagging. Use when assessing acquisition quality, choosing a cleaning tool, ordering QC relative to compensation, deciding margin removal before density-based steps, or flagging problematic samples before clustering or differential analysis.

## Instructions

## Version Compatibility

Reference examples tested with: flowAI 1.32+, PeacoQC 1.12+, flowCore 2.14+, flowDensity 1.36+, CATALYST 1.26+.

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

Counterintuitive defaults to confirm: flowAI checks are FR/FS/FM (FM = dynamic range, not "flow"); PeacoQC `MAD`/`IT_limit` are LESS strict when HIGHER. Verify with `?flow_auto_qc` and `?PeacoQC` before tuning.

# Cytometry QC

**"Run quality control on my cytometry data"** -> Detect and remove acquisition artifacts (flow-rate instability, signal drift, margin events, dead cells, CyTOF doublets) on the Time axis, then flag outlier samples.
- R (flow/spectral): `flowAI::flow_auto_qc()`, `PeacoQC::PeacoQC()` (+ `RemoveMargins()`)
- R (mass): `CATALYST::normCytof()` beads + Gaussian/DNA/event-length gating

## The Single Most Important Modern Insight -- The Time Parameter Is the Master QC Axis, and Order Matters

Nearly every acquisition artifact - clogs, bubbles, flow-rate surges, electronics warm-up, CyTOF sensitivity decay, oxide buildup - manifests as a CHANGE IN SIGNAL versus the Time channel. flowAI, flowCut, flowClean, and PeacoQC are all, at heart, Time-vs-signal anomaly detectors; a missing or mis-scaled `$TIMESTEP` silently degrades or breaks all of them. Just as important is the ORDER: compensation/unmixing -> transform -> margin removal -> time-based QC -> debris/doublet/dead-cell gating -> batch normalization. Margin (boundary) events piled at a detector min/max form spurious high-density ridges that fool density-based cleaning and density gates, so they must be stripped BEFORE any density step; and time-based QC on untransformed data misbehaves because the density structure the algorithms rely on lives on the transformed scale.

## Cleaning-Tool Taxonomy

| Tool | Citation | Mechanism | When to use / caveat |
|------|----------|-----------|----------------------|
| flowAI | Monaco 2016 *Bioinformatics* 32:2473 | 3 checks: flow rate (FR), signal acquisition (FS), dynamic range (FM) | classic; known AGGRESSIVE - can remove normal data |
| PeacoQC | Emmaneel 2022 *Cytometry A* 101:325 | per-channel density peaks + MAD + isolation tree | only tool validated across flow + mass + spectral; QC engine of CytoPipeline |
| flowCut | Meskas 2023 *Cytometry A* 103:71 | segments Time, removes low-density/deviant segments | less aggressive than flowAI; flags whole files |
| flowClean | Fletez-Brant 2016 *Cytometry A* 89:461 | tracks subset frequency in centered-log-ratio space | floor ~30,000 events; writes a "GoodVsBad" parameter to gate on |

## Run flowAI (with the correct API)

**Goal:** Auto-clean a sample for flow-rate, signal-acquisition, and dynamic-range anomalies.

**Approach:** `flow_auto_qc()` returns a flowFrame of high-quality events when `output=1`; FM is the dynamic-range check; supply `timeCh` for concatenated/clock-reset files. flowAI is the time-based QC step - run it after compensation/transform/margin removal (per the ordering above), not on a raw uncompensated frame.

```r
library(flowAI)

ff_clean <- flow_auto_qc(ff,
                         remove_from = 'all',          # FR + FS + FM
                         output = 1,                    # 1 = HQ events only; 2 = add QC param; 3 = bad-event IDs
                         ChExcludeFS = c('FSC', 'SSC'), # scatter excluded from the signal check
                         second_fractionFR = 0.1,
                         folder_results = 'qc_output')
cat('kept', nrow(ff_clean), 'of', nrow(ff), 'events\n')
```

## Margins First, Then PeacoQC

**Goal:** Remove boundary events, then clean unstable time/peak structure across all channels.

**Approach:** `RemoveMargins()` strips detector-min/max events; then `PeacoQC()` - remember higher `MAD`/`IT_limit` = LESS strict.

```r
library(PeacoQC)

ff_nm <- RemoveMargins(ff, channels = c('FSC-A', 'SSC-A'))   # do this BEFORE density QC
res <- PeacoQC(ff_nm, channels = marker_channels,
               MAD = 6, IT_limit = 0.55,                     # defaults; higher = less strict (counterintuitive)
               save_fcs = FALSE, plot = TRUE)
ff_clean <- res$FinalFF
```

## Dead-Cell, Drift, and CyTOF Checks

**Goal:** Exclude dead cells, detect per-channel drift, and apply CyTOF-specific gates.

**Approach:** Viability dye threshold (bimodal); per-time-bin median slope for drift; for CyTOF use DNA intercalator + Gaussian/event-length; EQ-bead-median-vs-Time is the primary CyTOF drift readout (see bead-normalization).

```r
expr <- exprs(ff)
# dead cells take up more viability dye -> cut at the bimodal density VALLEY (data-driven), not a fixed quantile
dead_cut <- flowDensity::deGate(ff, channel = 'Live_Dead')
live <- expr[, 'Live_Dead'] < dead_cut

# CyTOF single-cell gates
if ('Event_length' %in% colnames(expr)) {
    keep <- expr[, 'Event_length'] >= 10 & expr[, 'Event_length'] <= 75   # confirm range per instrument
}
dna <- grep('Ir191|Ir193', colnames(expr), value = TRUE)             # intercalator-positive = nucleated
```

## Calibration and Standardization (cross-study comparability)

A discovery analyst often skips this, but cross-experiment/cross-site MFI comparison is meaningless without it (Maecker & Trotter 2006 *Cytometry A* 69:1037):
- **MESF / MEF / ERF** beads express intensity in molecules-of-equivalent-fluorochrome - comparable across instruments and time (NIST/ISAC standard; PE/Pacific Blue use ERF surrogates).
- **Quantibrite PE** (defined PE molecules/bead, ~1:1 conjugation) converts MFI to antibodies-bound-per-cell / receptor density (bead values are LOT-dependent).
- **CS&T / 8-peak rainbow beads** for daily QC (laser delay, area scaling, linearity).
- **Peak-2 / voltration**: run a dim particle across PMT voltages, pick the CV-vs-voltage inflection = minimum voltage for optimal resolution. This is why MIFlowCyt mandates reporting voltages.

## Batch-Level Outlier Flagging

**Goal:** Flag samples whose event count, flow stability, or marker medians deviate from the batch.

**Approach:** Per-file metrics + MAD-based bounds; track an anchor/reference sample if present.

```r
qc <- do.call(rbind, lapply(fcs_files, function(f) {
  ff <- read.FCS(f); e <- exprs(ff)
  data.frame(file = basename(f), events = nrow(ff),
             med_signal = median(apply(e, 2, median)))
}))
qc$outlier <- abs(qc$events - median(qc$events)) > 3 * mad(qc$events)
```

## Per-Method Failure Modes

### Density QC on un-margin-removed data
**Trigger:** PeacoQC/flowClean before `RemoveMargins`. **Mechanism:** axis pile-ups are false high-density ridges. **Symptom:** real events removed near the boundary, or margins kept. **Fix:** remove margins first.

### flowAI over-removal
**Trigger:** default flowAI on a low-rate or short acquisition. **Mechanism:** FR check flags normal slow segments. **Symptom:** large unexplained event loss. **Fix:** raise `second_fractionFR`; inspect the HTML report; consider flowCut/PeacoQC.

### QC on untransformed/uncompensated data
**Trigger:** running QC on raw linear values. **Mechanism:** high-intensity tail dominates density. **Symptom:** misplaced anomaly calls. **Fix:** compensate + transform first.

### Time axis missing/reset
**Trigger:** concatenated files, some sorters. **Mechanism:** no usable Time. **Symptom:** flow-rate check fails or is meaningless. **Fix:** `timeCh=` or reconstruct; otherwise skip time-based checks.

## Quantitative Thresholds

| Threshold | Source | Rationale |
|-----------|--------|-----------|
| flowClean floor ~30,000 events | Fletez-Brant 2016 *Cytometry A* 89:461 | below this the CLR frequency tracking under-detects |
| PeacoQC `MAD=6`, `IT_limit=0.55` | Emmaneel 2022 *Cytometry A* 101:325 | defaults; HIGHER = less strict |
| dead cells > ~10-30% | community | sample-handling flag, not a hard cutoff - report, don't auto-exclude the sample |
| CyTOF retune ~ daily / per long run | instrument practice (flagged) | sensitivity decays from cone fouling/plasma drift |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| `flow_auto_qc` returns unexpected object | assuming `$fcs`/report list | `output=1` returns a flowFrame; set `output` explicitly |
| margins not removed by PeacoQC | expecting it built-in | call `RemoveMargins()` separately, first |
| tuning MAD up removes more | sign confusion | higher MAD/IT_limit = LESS strict |
| flowClean output unchanged | it appends a parameter | gate on the "GoodVsBad" column |

## References

- Monaco 2016 *Bioinformatics* 32(16):2473-2480 — flowAI.
- Emmaneel 2022 *Cytometry A* 101(4):325-338 — PeacoQC.
- Meskas 2023 *Cytometry A* 103(1):71-81 — flowCut.
- Fletez-Brant 2016 *Cytometry A* 89(5):461-471 — flowClean.
- Fienberg 2012 *Cytometry A* 81(6):467-475 — cisplatin viability reagent (CyTOF live/dead).
- Maecker & Trotter 2006 *Cytometry A* 69(9):1037-1042 — controls, instrument setup, peak-2.
- Lee 2008 *Cytometry A* 73(10):926-930 — MIFlowCyt reporting (voltages, clones, config).

## Related Skills

- compensation-transformation - Compensate/transform before time-based QC
- doublet-detection - Singlet discrimination after QC
- bead-normalization - EQ-bead drift correction for CyTOF (QC's normalization arm)
- clustering-phenotyping - Cluster only QC-passed events
- experimental-design/batch-design - Anchor/reference-sample design for batch QC

## Usage Guide

# Cytometry QC - Usage Guide

## Overview
Quality control detects and removes acquisition artifacts before any downstream analysis. The Time parameter is the master axis: flow-rate instability, signal drift, clogs, and CyTOF sensitivity decay all show up as signal-versus-time anomalies, which is what flowAI, flowCut, flowClean, and PeacoQC detect. This skill covers tool selection, the mandatory QC ordering (compensate -> transform -> margins -> time QC -> gating), CyTOF-specific checks, the instrument calibration/standardization machinery (MESF, CS&T, peak-2) that makes cross-study comparison possible, and batch-level outlier flagging.

## Prerequisites
```bash
# R/Bioconductor
BiocManager::install(c('flowCore', 'flowAI', 'PeacoQC', 'flowDensity', 'CATALYST'))
```

## Quick Start
Tell your AI agent what you want to do:
- "Run automated QC on my FCS files and tell me what was removed"
- "Remove margin events, then clean unstable time segments with PeacoQC"
- "Check my CyTOF run for signal drift and gate single nucleated cells"
- "Flag outlier samples across my batch"

## Example Prompts
### Event-level cleaning
> "Run flowAI on these files but it's removing too much - it's a slow acquisition, so tune the flow-rate sensitivity and show me the report before committing."
> "Remove margin/boundary events first, then apply PeacoQC across the marker channels - and explain why margins have to go before the density step."

### CyTOF and drift
> "This is a multi-day CyTOF study - check EQ-bead signal versus time for drift and gate intercalator-positive single cells by Event_length and Gaussian parameters."
> "Detect per-channel signal drift over acquisition time and tell me which markers exceed 10% change."

### Calibration and batch QC
> "Convert my PE MFI to antibodies-bound-per-cell using Quantibrite beads."
> "Build a per-sample QC table (events, flow-rate stability, marker medians) and flag outliers by MAD."

## What the Agent Will Do
1. Confirm data is compensated and transformed (QC on raw data misbehaves).
2. Remove margin/boundary events before any density-based step.
3. Run time-based cleaning with the appropriate tool (flowAI/flowCut/PeacoQC) and the correct, non-inverted parameters.
4. Apply instrument-specific checks (dead-cell dye for flow; DNA/Event_length/Gaussian + bead drift for CyTOF).
5. Summarize per-sample metrics and flag outliers; report what was removed.

## Tips
- Order matters: compensate -> transform -> margins -> time-based QC -> gating -> normalization.
- flowAI checks are FR (flow rate) / FS (signal) / FM (dynamic range) - FM is not "flow"; flowAI is known to be aggressive.
- PeacoQC `MAD` and `IT_limit` are LESS strict when higher (counterintuitive); run `RemoveMargins()` first.
- PeacoQC is the only cleaning tool validated across flow, mass, and spectral.
- flowClean needs ~30,000+ events and writes a "GoodVsBad" parameter you must gate on.
- For CyTOF, EQ-bead-median-vs-Time is the single most informative drift readout (see bead-normalization).
- Report dead-cell % and outlier samples; don't silently auto-exclude a whole sample without inspection.
- Cross-study MFI comparison requires calibration (MESF/ERF beads, CS&T, standardized voltages via peak-2) - record voltages per MIFlowCyt.

## Related Skills
- compensation-transformation - Compensate/transform before time-based QC
- doublet-detection - Singlet discrimination after QC
- bead-normalization - EQ-bead drift correction for CyTOF
- clustering-phenotyping - Cluster only QC-passed events
- experimental-design/batch-design - Anchor/reference-sample design for batch QC

## Bundled Files

- `flow-cytometry--cytometry-qc--examples--run_qc.R` — copied from `examples/run_qc.R`
