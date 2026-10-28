# Liquid Biopsy Pipeline - Usage Guide

## Overview
Complete cell-free DNA analysis workflow from plasma sequencing to clinical interpretation. Supports both shallow WGS for tumor fraction estimation and targeted panels for mutation detection.

## Prerequisites
```bash
# cfDNA preprocessing
conda install -c bioconda fgbio bwa samtools

# Tumor fraction (sWGS)
# R: devtools::install_github('GavinHaLab/ichorCNA')

# Mutation detection (panel)
conda install -c bioconda vardict-java

# Fragmentomics
pip install finaletoolkit pysam pandas numpy matplotlib
```

## Quick Start
Tell your AI agent what you want to do:
- "Analyze my plasma cfDNA sequencing data"
- "Estimate tumor fraction from shallow WGS"
- "Detect ctDNA mutations from my targeted panel"
- "Run a complete liquid biopsy pipeline"

## Example Prompts

### Full Pipeline
> "I have plasma cfDNA from a targeted panel with UMIs. Run a complete analysis."

> "Set up a liquid biopsy pipeline for my sWGS samples."

### Specific Analyses
> "Preprocess my cfDNA BAM with UMI consensus calling."

> "Run ichorCNA to estimate tumor fraction from my 0.5x sWGS."

> "Detect mutations at 0.5% VAF and filter out CHIP variants."

> "Track ctDNA levels across my serial samples."

## What the Agent Will Do
1. Check pre-analytical quality factors
2. Preprocess with UMI-aware deduplication
3. Verify cfDNA quality (fragment size distribution)
4. Estimate tumor fraction (sWGS) OR detect mutations (panel)
5. Filter CHIP variants
6. Optionally analyze fragmentomics
7. Track longitudinal dynamics if serial samples

## Tips
- sWGS (0.1-1x) is for tumor fraction; panels are for mutations
- ichorCNA detects >= 3% tumor fraction reliably; below that floor, route to fragmentomics or methylation
- VarDict detects >= 0.5% VAF with UMI consensus; duplex consensus extends toward 0.1% and below
- Detection limit is set by genome-equivalents sampled and error suppression, not sequencing depth; report LoD conditioned on input mass
- CHIP is the dominant plasma false positive; sequence matched buffy-coat/WBC and subtract, do not rely on a gene list alone
- Pre-analytical factors matter: use Streck tubes or process EDTA quickly
- FinaleToolkit replicates DELFI patterns (DELFI is a methodology and company, not software)

## Related Skills
- references/liquid-biopsy--cfdna-preprocessing.md - UMI/duplex consensus error suppression
- references/liquid-biopsy--analytical-validation.md - molecule-counting limits of detection
- references/liquid-biopsy--ctdna-mutation-detection.md - low-VAF calling and CHIP subtraction
- references/liquid-biopsy--tumor-fraction-estimation.md - ichorCNA analysis
- references/liquid-biopsy--fragment-analysis.md - Fragmentomics
- references/liquid-biopsy--methylation-based-detection.md - methylation detection and tissue-of-origin
- references/liquid-biopsy--longitudinal-monitoring.md - Serial tracking
