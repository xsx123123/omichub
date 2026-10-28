# bio-crispr-screens-in-vivo-screens

> Bundled component reference for `crispr-screens/in-vivo-screens` (original source: `skills/bio_skills/crispr-screens/in-vivo-screens`).

Designs and analyzes in vivo CRISPR screens in animal tumor models, organoids, and immune-cell adoptive transfers. Covers bottleneck math (250x cells/sgRNA requires ~25M cells implanted; impossible for most syngeneic models, forcing focused libraries), focused library design (Manguso 2017 Nature 547:413 immune screen; Chen 2015 tumor screens), CRISPR-StAR intrinsic-control screening (Uijttewaal 2025 Nat Biotechnol 43:1848), clonal-dynamics-limited detection, tumor-explant DNA recovery, syngeneic vs xenograft vs PDX considerations, and the relationship to downstream MAGeCK / drugZ analysis. Use when designing in vivo CRISPR screens for tumor / immune / metastasis biology, choosing focused vs genome-wide for animal models, addressing bottleneck-induced clonal collapse, picking the syngeneic / xenograft / PDX model, integrating in vivo with in vitro results, or applying CRISPR-StAR for animal experiments.

## Instructions

## Version Compatibility

Reference examples tested with: MAGeCK 0.5.9+, MAGeCK-VISPR 0.5.6+, pandas 2.2+, numpy 1.26+.

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `mageck --version`
- Reference focused libraries: Manguso 2017, Chen 2015, public Addgene aliquots

If code throws ImportError, AttributeError, or TypeError, introspect the installed package and adapt the example to match the actual API rather than retrying.

## In Vivo CRISPR Screen Analysis

**"Design or analyze an in vivo CRISPR screen"** -> Account for the dramatic bottleneck during animal implantation and tumor growth; use focused libraries; recover DNA from tumor explants; analyze with bottleneck-adjusted hit calling.

- CLI: `mageck count` + `mageck test` for standard analysis
- Special handling: bottleneck-adjusted coverage thresholds; per-tissue per-animal replicate structure

## The In Vivo Bottleneck Problem

**Why in vivo screens differ from in vitro:**

| Constraint | In vitro | In vivo |
|------------|----------|---------|
| Cells per condition | 10M-100M (unlimited) | Limited by injection volume (1-5M cells typical) |
| Implant -> early tumor cell count | N/A | 10-100x drop typical |
| Late tumor cell count | N/A | Further 5-10x reduction; ~4 sgRNAs/gene retained in late tumors (Scheidmann 2022) |
| Bottleneck per animal | None | Tens of millions of cells fail to engraft |
| Library coverage achievable | 500-1000x | Often 50-100x effective at endpoint |
| sgRNAs survivable | Full library | 66-97% in early (14 d) tumors, strongly cell-line dependent (Lee 2023); by 38-43 d most reads come from the top 1% of guides |

**Math:** A 70,000-sgRNA library at 500x coverage requires 35M cells in pool. Most syngeneic models can implant 1-5M cells. Result: real coverage is 70x at best; effective coverage at endpoint is even lower after bottleneck.

**Solution:** Use focused libraries (500-3,000 genes; ~3,000-15,000 sgRNAs) to maintain reasonable coverage despite the bottleneck.

## Focused Library Design for In Vivo

**Manguso et al 2017 *Nature* 547:413** established the canonical in vivo CRISPR screen methodology with a focused library:

- 2,398 genes covering kinases, phosphatases, cell-surface proteins, antigen presentation, immune regulation and chromatin remodeling; the 2,368 expressed in the melanoma line were the ones scored
- 4 sgRNAs per gene, delivered as four sub-pools of one sgRNA per gene plus 100 non-targeting controls each (9,992 sgRNAs total)
- Targeted at immune-evasion biology in syngeneic mouse melanoma
- Recovered the known immune-evasion genes Cd274 (PD-L1) and Cd47, and identified Ptpn2 loss as sensitizing tumors to immunotherapy through increased IFN-gamma signaling and antigen presentation

**Standard focused-library principles:**

1. **Gene selection:** Define the biology to be tested (e.g., immune evasion, metastasis); restrict library to genes plausibly involved (kinases, surface proteins, regulators)
2. **Library size:** 500-3,000 genes; 3-6 sgRNAs/gene; total 3,000-18,000 sgRNAs
3. **Coverage achievable:** With 5M cells implanted, 100-300x coverage is achievable

**Public focused libraries:**
- Manguso 2017 immune library (Addgene)
- DepMap focused panels for specific pathways
- Custom: order from Twist via CRISPick or CRISPOR

## CRISPR-StAR (Stochastic Activation by Recombination; Uijttewaal 2025)

**Uijttewaal et al 2025 *Nat Biotechnol* 43(11):1848** (published online Dec 2024) introduced CRISPR-StAR, which holds sgRNAs inactive until cells have engrafted and re-expanded, then activates each sgRNA in only half the progeny of a clone to generate matched active-vs-inactive internal controls.

**How it works:**
1. Library is delivered as sgRNAs held in an inactive state, alongside a tamoxifen-inducible CreERT2 recombinase
2. Cells are implanted in animal at MOI 0.3; they engraft and re-expand into single-cell-derived clones (no editing yet); library complexity preserved
3. Tamoxifen induces CreERT2 recombination, which stochastically activates the sgRNA in ~half the cells of each clone
4. Active and still-inactive (wild-type) cells of the same clone, tracked by UMI barcodes, form paired internal active-vs-control comparisons
5. Screen proceeds; tumor harvest, DNA extraction, sequencing
6. Per-clone active-vs-inactive contrast suppresses engraftment and clonal-drift noise

**What it buys:** CRISPR-StAR enables genome-scale in vivo screens (vs focused libraries) by generating intrinsic per-clone controls; outperforms conventional in vivo screens in therapy-resistant mouse melanoma models (Uijttewaal 2025).

## Syngeneic vs Xenograft vs PDX

| Model | Immune system | Use case |
|-------|---------------|----------|
| Syngeneic (e.g., B16 melanoma in C57BL/6) | Intact mouse immunity | Tumor-immune interaction; checkpoint biology |
| Xenograft (human cancer line in NSG) | Absent / impaired | Tumor cell-intrinsic biology; drug response in human cells |
| PDX (patient-derived xenograft) | Absent / impaired | Patient-specific biology; therapy testing |
| Humanized mouse | Reconstituted human immunity | Tumor-immune in human context (limited) |
| Organoid in vivo | None (in vitro) | Tumor cell-intrinsic in 3D structure |

**Decision rule:** For immune-targeting drug screens, use syngeneic. For human-cancer cell-intrinsic biology, use xenograft. For patient-specific drug screens, use PDX. Each requires different cell numbers and bottleneck planning.

## Tumor DNA Extraction and Sequencing

**Goal:** Recover sufficient sgRNA-containing DNA from tumor explants for sequencing.

**Approach:** Dissect tumor; lyse with proteinase K; extract genomic DNA; amplify the sgRNA locus by PCR; sequence on MiSeq / NextSeq / NovaSeq.

```bash
# Typical PCR + sequencing parameters for in vivo screens
# Per-tumor DNA: 0.5-5 mg yield from typical syngeneic tumor
# Per-sample sequencing depth: >=500 reads/sgRNA at endpoint (bottleneck-limited libraries need depth, not breadth)
# Multiple animals per condition (n=5-10) to account for clonal variation

# mageck count for in vivo
mageck count \
    --list-seq library.csv \
    --sample-label Plasmid,Animal1,Animal2,Animal3,Animal4,Animal5 \
    --fastq Plasmid.fq.gz A1.fq.gz A2.fq.gz A3.fq.gz A4.fq.gz A5.fq.gz \
    --norm-method median \
    --output-prefix in_vivo_screen
```

## Hit Calling for In Vivo

**Goal:** Identify per-gene fitness effects despite high inter-animal variability.

**Approach:** Each animal is a "replicate" with high variance due to clonal dynamics. Use MAGeCK MLE with animal-as-batch covariate, or run MAGeCK RRA per animal and meta-analyze.

```bash
# Option A: MAGeCK MLE with batch covariate
cat > in_vivo_design.txt <<EOF
Samples         baseline    tumor   animal_2  animal_3  animal_4  animal_5
Plasmid         1           0       0         0         0         0
Animal1         1           1       0         0         0         0
Animal2         1           1       1         0         0         0
Animal3         1           1       0         1         0         0
Animal4         1           1       0         0         1         0
Animal5         1           1       0         0         0         1
EOF

mageck mle \
    --count-table in_vivo_screen.count.txt \
    --design-matrix in_vivo_design.txt \
    --output-prefix in_vivo_mle
```

**Per-animal RRA + meta-analysis:**

```python
import pandas as pd

# Run mageck test on each animal vs plasmid
# Combine with Stouffer's Z method
from scipy.stats import norm

def meta_analyze_animals(per_animal_results):
    '''per_animal_results: list of MAGeCK gene_summary.txt per animal.'''
    merged = pd.concat([df.assign(animal=i) for i, df in enumerate(per_animal_results)])
    grouped = merged.groupby('id')
    meta = grouped.apply(lambda g: pd.Series({   # pandas 2.2+: pass include_groups=False
        'mean_neg_score': g['neg|score'].mean(),
        # clip to keep norm.ppf finite at p=0; negate so positive z = stronger depletion,
        # matching crispr-screens--in-vivo-screens--examples--per_animal_meta_analysis.py
        'stouffer_z': -norm.ppf(g['neg|p-value'].clip(1e-10, 1 - 1e-10)).sum() / (len(g) ** 0.5),
        'animals_significant': (g['neg|fdr'] < 0.05).sum(),
        'n_animals': len(g)
    }))
    return meta.sort_values('stouffer_z')
```

## Failure Modes

### Clonal dominance from low complexity

**Trigger:** Implanted cells lack sufficient library complexity; a few clones dominate the tumor.
**Mechanism:** Inter-animal stochasticity in cell engraftment creates founder effects.
**Symptom:** Per-animal hit lists vary dramatically; no genes appear across all animals.
**Fix:** Use focused library to maintain coverage; increase animals per condition (n=10+); use CRISPR-StAR to delay bottleneck.

### Tumor DNA extraction yields no sgRNA reads

**Trigger:** Wrong library or library not amplified well from tumor DNA.
**Mechanism:** PCR primers don't match the sgRNA flanking; or insufficient DNA template.
**Symptom:** Low mapping rate (<10%); few sgRNAs detected per tumor.
**Fix:** Verify library plasmid sequence; design primers specific to lentiviral cassette; use 10-100 ng input DNA + 25 PCR cycles.

### In vivo PR-AUC against CEGv2 is poor

**Trigger:** Tumor biology differs from in vitro CEGv2 calibration; not all essentials are essential in animal context.
**Mechanism:** Cells in vivo have different growth conditions (nutrients, hypoxia, immune pressure) than in vitro; CEGv2 calibration assumes in vitro context.
**Symptom:** CEGv2 PR-AUC <0.5 in vivo despite high in vitro PR-AUC.
**Fix:** Use cell-type-and-context-specific essentialome (e.g., a corresponding in vitro screen of the same cell type) as a baseline; in vivo essentialome is biology-dependent.

### Pre-screen Cas9 selection failure

**Trigger:** Cas9-positive cells were not selected before implantation; library has Cas9-negative escapers.
**Mechanism:** Cas9-negative cells carry sgRNA but no editing; persist in tumor without biological perturbation.
**Symptom:** Specific essentiality signals weak; PR-AUC low.
**Fix:** Always select Cas9-positive cells (FACS or selection) before infection; verify by Cas9 IHC or flow.

### Inter-animal variability dominates hit calling

**Trigger:** Limited animals per condition (n=3-5); each has high variance.
**Mechanism:** Per-animal clonal dynamics produce different sgRNA distributions; no consistent signal across few animals.
**Symptom:** MAGeCK p-values inflated; FDR uncalibrated.
**Fix:** Increase animals per condition to 10+; use meta-analysis across animals (Stouffer); validate top hits in arrayed format with n=10 mice each.

### Tumor heterogeneity destroys screen signal

**Trigger:** Spontaneously arising mutations in some tumor regions create non-clonal heterogeneity.
**Mechanism:** Tumor heterogeneity is genuine biology; not all cells in tumor are descendants of original engrafted cells.
**Symptom:** Per-region sequencing shows different sgRNA distributions within same tumor.
**Fix:** Sample multiple tumor regions; or use whole-tumor genomic DNA pooling (averages out heterogeneity).

## Quantitative Thresholds

| Threshold | Value | Source / Rationale |
|-----------|-------|--------------------|
| Cells per animal | 1-5M typical for syngeneic; 5-10M for xenograft | Tumor model dependent |
| sgRNAs per gene in library (focused) | 4-6 | Standard convention |
| Library size for in vivo focused | 3,000-15,000 sgRNAs | Maintainable coverage |
| Coverage at endpoint | ≥50x, ideally 100-200x | Lower than in vitro 500x |
| Animals per condition | 10+ for hit-calling; 5 minimum | Inter-animal variability |
| Animals per condition for arrayed validation | 10 | Tighter signal needed |
| In vivo CEGv2 PR-AUC | >0.4 (context-dependent) | Lower than in vitro 0.7 |
| Late tumor sgRNA-per-gene | ~3.93 mean | Scheidmann 2022 (CTC-derived breast-cancer xenograft; model-dependent) |
| Days to harvest (tumor) | 12-21 days post-implant | Time for selection to manifest |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| No hits | Library complexity collapsed | Use focused library or CRISPR-StAR |
| Per-animal hit lists differ | Clonal dominance | Use focused library; increase animals |
| Low CEGv2 PR-AUC | Context-specific essentialome | Use in vivo-specific reference set |
| Low mapping rate | Wrong sequencing primers | Verify library lentiviral architecture |
| Coverage at endpoint <50x | Implantation bottleneck | Increase cells implanted; focused library |

## References

- Manguso RT et al. 2017. *Nature* 547:413. In vivo CRISPR screen for immune evasion; canonical focused-library design.
- Chen S et al. 2015. *Cell* 160:1246. Original in vivo Cas9 screening methodology.
- Lee TW et al. 2023. *Cancer Gene Ther* 30:1610. Clonal dynamics limit detection of selection in tumour xenograft CRISPR/Cas9 screens.
- Scheidmann MC et al. 2022. *Cancer Res* 82:681. In vivo CRISPR screen in a CTC-derived xenograft; late-tumor sgRNA-per-gene retention.
- Uijttewaal ECH et al. 2025. *Nat Biotechnol* 43:1848 (online Dec 2024). CRISPR-StAR intrinsic-control screening for in vivo models.

## Related Skills

- crispr-screens/library-design - Focused library design for in vivo
- crispr-screens/mageck-analysis - MAGeCK MLE with animal-as-batch covariate
- crispr-screens/hit-calling - Per-animal meta-analysis strategies
- crispr-screens/screen-qc - In-vivo-specific QC thresholds
- crispr-screens/batch-correction - Animal cohort as batch in MLE
- crispr-screens/combinatorial-screens - In vivo combinatorial screens
- crispr-screens/copy-number-correction - Cancer-line in vivo screens
- pathway-analysis/go-enrichment - Functional analysis of in vivo hits

## Usage Guide

# In Vivo CRISPR Screens - Usage Guide

## Overview

Decision-grade design and analysis of in vivo CRISPR screens. Covers the bottleneck math (cell number limits force focused libraries); Manguso 2017 immune-evasion methodology; Chen 2015 tumor screens; CRISPR-StAR stochastic post-engraftment sgRNA activation (Uijttewaal 2025 Nat Biotechnol 43:1848) for escaping early bottlenecks; syngeneic vs xenograft vs PDX choice; per-animal clonal variability; tumor-explant DNA extraction; per-animal meta-analysis; in vivo CEGv2 calibration limitations.

## Prerequisites

```bash
conda install -c bioconda mageck   # not on PyPI
pip install pandas numpy scipy
# Optional: focused library annotations from Manguso 2017
# Tumor genomic DNA extraction kit (proteinase K + column purification)
```

Required inputs:
- Animal cohorts (n=10+ per condition for hit calling)
- Focused library (3,000-15,000 sgRNAs covering 500-3,000 genes)
- Cas9+ cell line (selected by FACS before infection)
- Plasmid pool sequencing as baseline
- Per-animal tumor DNA + sgRNA amplification primers

## Quick Start

Tell the AI agent what to do:
- "Design a focused in vivo CRISPR library targeting immune-evasion biology following Manguso 2017 methodology: 2,000 kinases + surface proteins + immune factors, 4 sgRNAs/gene"
- "Compute bottleneck math: my B16 syngeneic model can take 2M cells; pick library size for 100x coverage maintainable through bottleneck"
- "Apply CRISPR-StAR so a genome-scale library survives the in vivo bottleneck: activate sgRNAs after engraftment for paired internal controls"
- "Run MAGeCK MLE on my in vivo screen with animal-as-batch covariate; output per-condition beta scores after batch adjustment"
- "Diagnose: why is my in vivo CEGv2 PR-AUC only 0.45 despite passing all in vitro QC?"

## Example Prompts

### Library Design for In Vivo

> "Design a focused library targeting immune-evasion biology in syngeneic B16-OVA mouse melanoma. Include: kinases, cell surface proteins, immune-regulatory genes (Manguso 2017 selection criteria). Total ~2,000 genes x 4 sgRNAs = 8,000 sgRNAs. Verify coverage with 2M cells implanted (= 250x cells/sgRNA before the engraftment bottleneck)."

> "For a syngeneic colorectal cancer model with maximum 3M cells implantable: design library at 5,000 sgRNAs (= 600x effective coverage). Pick genes by pathway relevance (metabolism, immune, proliferation)."

### CRISPR-StAR

> "Set up CRISPR-StAR (Uijttewaal 2025) screen with tamoxifen-inducible CreERT2 sgRNA activation in a syngeneic model. Cells infected with library at MOI 0.3; implanted in 5 mice per condition; tamoxifen induction Day 5 post-implant activates the sgRNA in ~half of each clone for paired internal controls; tumor harvest Day 21. Compute expected coverage maintenance vs a conventional in vivo screen."

### Per-Animal Analysis

> "Run MAGeCK on each animal vs plasmid pool separately; meta-analyze with Stouffer's Z; identify genes consistent across animals. Compare to single combined-animal analysis."

> "Run MAGeCK MLE with animal as batch covariate. Output per-condition beta after batch adjustment. Compare to per-animal RRA + meta-analysis."

### Diagnostics

> "In vivo CEGv2 PR-AUC is 0.45 despite in vitro on same line showing 0.85. Diagnose: context-specific essentialome, clonal dominance, or Cas9 selection failure?"

> "My screen has 100x effective coverage at endpoint but only 60% of library detected. Investigate: bottleneck at engraftment or PCR amplification?"

### Cross-Validation

> "Validate top in vivo hits in vitro (matched cell line, no animal context). Identify hits that are in-vivo-specific (require tumor microenvironment) vs cell-intrinsic."

> "Arrayed validation of top 10 in vivo hits with n=10 mice each. Confirm consistent effect across biological replicates."

## What the Agent Will Do

1. Determine model: syngeneic vs xenograft vs PDX
2. Calculate bottleneck-adjusted library size: max cells implantable × target coverage = total sgRNAs
3. Design focused library following Manguso 2017 conventions
4. Plan animal cohort: n=10+ per condition for hit calling
5. Use CRISPR-StAR if genome-scale library needed (CreERT2 sgRNA activation in half of each clone + post-engraftment induction)
6. Verify Cas9+ cell selection before infection (FACS or selection marker)
7. Sequence plasmid pool as baseline
8. Implant cells; allow tumor growth 12-21 days
9. Harvest tumors; extract DNA via proteinase K + column purification
10. PCR amplify sgRNA cassette + sequence
11. Run MAGeCK count + MLE with animal as batch covariate (or RRA per animal + meta-analysis)
12. QC: in vivo-adjusted thresholds (CEGv2 PR-AUC >0.4 acceptable; lower than in vitro)
13. Per-condition hit calling; cross-validate with in vitro
14. Output: per-condition gene effects, per-animal consistency, arrayed validation plan

## Tips

- The single most common failure: trying to use a genome-wide library (70k+ sgRNAs) in vivo. Even at 10M cells implanted, this gives 140x coverage which collapses to 20-50x at endpoint after bottleneck. Use focused libraries unless implementing CRISPR-StAR.
- For immune-targeting screens, syngeneic models are mandatory; xenografts have impaired immunity.
- Per-animal clonal dynamics drive enormous inter-animal variability. Use n=10+ animals per condition; meta-analyze across animals rather than treating as single experiment.
- Cas9 selection before implantation is non-negotiable. Cas9-negative cells persist with their sgRNA but no editing, diluting all signal.
- In vivo CEGv2 calibration is poor because in vitro essentialome doesn't capture tumor-microenvironment biology. Use cell-type-and-context-specific reference essentialome (a matched in vitro screen in the same cell type).
- CRISPR-StAR is the modern approach for genome-scale in vivo: hold sgRNAs inactive until after engraftment, then activate (tamoxifen/CreERT2) in half of each clone for paired internal controls. Uijttewaal 2025 (Nat Biotechnol 43:1848) reports intrinsic per-clone control and outperforms conventional screens in therapy-resistant melanoma models.
- Multiple animals per condition is more important than depth per animal. n=10 mice at 100x coverage is better than n=3 at 500x.
- Tumor heterogeneity arises during growth; sample multiple regions or pool whole-tumor DNA.
- For metastasis screens, each metastatic site is a separate selection event; analyze per-site.

## Decision Cheat Sheet

| Model | Use case |
|-------|----------|
| Syngeneic | Tumor-immune interaction, checkpoint biology |
| Xenograft | Human cancer cell-intrinsic biology |
| PDX | Patient-specific drug testing |
| Humanized mouse | Tumor-immune in human context |

## Thresholds

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Cells per animal (syngeneic) | 1-5M typical | Tumor model dependent |
| Library size for focused in vivo | 3,000-15,000 sgRNAs | Maintainable coverage |
| sgRNAs per gene in library | 4-6 | Standard |
| Coverage at endpoint | >50x; ideally 100-200x | Bottleneck-adjusted |
| Animals per condition for hit calling | 10+ | Inter-animal variability |
| In vivo CEGv2 PR-AUC | >0.4 acceptable | Lower than in vitro |
| Days to harvest | 12-21 days post-implant | Time for selection |

## Validation Checklist

- [ ] Library size matches bottleneck math
- [ ] Cas9+ cells selected before infection
- [ ] Plasmid pool sequenced as baseline
- [ ] n ≥10 animals per condition
- [ ] Per-animal sequencing depth ≥100 reads/sgRNA
- [ ] MAGeCK MLE with animal-as-batch covariate
- [ ] Cross-validation with in vitro screen
- [ ] Arrayed validation of top hits in matched cohort

## Related Skills

- crispr-screens/library-design - Focused library design
- crispr-screens/mageck-analysis - MAGeCK MLE with batch covariate
- crispr-screens/hit-calling - Per-animal meta-analysis
- crispr-screens/screen-qc - In vivo-specific QC
- crispr-screens/batch-correction - Animal cohort as batch
- crispr-screens/combinatorial-screens - In vivo combinatorial
- crispr-screens/copy-number-correction - Cancer-line in vivo
- pathway-analysis/go-enrichment - Functional analysis

## Bundled Files

- `crispr-screens--in-vivo-screens--examples--per_animal_meta_analysis.py` — copied from `examples/per_animal_meta_analysis.py`
