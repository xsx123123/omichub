# bio-crispr-screens-combinatorial-screens

> Bundled component reference for `crispr-screens/combinatorial-screens` (original source: `skills/bio_skills/crispr-screens/combinatorial-screens`).

Designs and analyzes combinatorial CRISPR screens covering paired-Cas9 (Big Papi, Najm 2018), enhanced AsCas12a multiplex (enCas12a, DeWeirdt 2021), in4mer 4-guide-array Cas12a (Esmaeili Anvar N et al 2024 Nat Commun 15:3577) and the Inzolia paralog-pair library, paralog-buffering detection (Dede 2020 Genome Biol; Thompson 2021 Nat Commun 12:1302), genetic-interaction (GI) scoring as observed_double_LFC minus expected_additive_double_LFC, synthetic-lethal and synthetic-rescue interaction interpretation, the half-of-essentiality buffered by paralogs phenomenon, multiplex screen statistical analysis with MAGeCK MLE interaction terms, and the relationship to single-cell combinatorial Perturb-seq. Use when designing a paralog or pathway-pair screen, choosing between paired-Cas9 (Big Papi) and Cas12a multiplex (Inzolia), interpreting genetic interaction scores, identifying synthetic-lethal targets for drug development, or scaling beyond single-gene CRISPR screens.

## Instructions

## Version Compatibility

Reference examples tested with: MAGeCK 0.5.9+ (for MLE with interaction terms), Inzolia library annotation (Esmaeili Anvar 2024), pandas 2.2+, numpy 1.26+, scipy 1.12+, matplotlib 3.8+.

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `mageck --version`; `mageck mle --help`
- For Cas12a libraries: verify against published Inzolia / in4mer / Big Papi annotations

If code throws ImportError, AttributeError, or TypeError, introspect the installed package and adapt the example to match the actual API rather than retrying.

## Combinatorial CRISPR Screen Analysis

**"Run a combinatorial CRISPR screen to find synthetic-lethal interactions"** -> Design a paired or multiplex library, screen for double-knockout fitness, score per-pair genetic interaction (GI = observed_double - expected_additive), and identify synthetic-lethal (negative GI) and synthetic-rescue (positive GI) interactions.

- CLI: `mageck mle` with explicit interaction terms for paired-Cas9 (Big Papi-style)
- Python: custom GI scoring for Cas12a multiplex (in4mer / Inzolia)
- Modality: enCas12a / LbCas12a single-array multiplex (preferred for paralog screens)

## Combinatorial Architecture Decision Tree

| Goal | Architecture | Library | Why |
|------|--------------|---------|-----|
| Paralog buffering, identify synthetic lethal paralog pairs | enCas12a single-array 4-guide multiplex | Inzolia (Esmaeili Anvar 2024) | Cas9 single-KO misses paralog-buffered essentials (42% of constitutively expressed genes never score, Dede 2020) |
| Test specific pathway pair (e.g., DNA repair branches) | Big Papi (orthologous SaCas9 + SpCas9; two sgRNAs from U6 and H1 in pPapi) | Custom | Mature methodology; orthologous enzymes avoid repeated-element recombination |
| Combinatorial 3-way / 4-way knockout | in4mer (4-guide single Cas12a array) | Custom (in4mer) | Single transcript processed by Cas12a; multi-gene |
| Single-cell Perturb-seq with multi-pert per cell | Combinatorial Perturb-seq + Cas9 multiplex | Custom | Single-cell readout of multi-perturbation effects |
| Drug-modifier + KO interaction | Cas9 KO + drug treatment | Standard libraries | Drug as second "perturbation" |

**Fails when:**
- Dual-sgRNA constructs built from repeated U6/tracr elements: lentiviral recombination collapses them to a single perturbation
- Cas12a screens analyzed as Cas9 screens: MAGeCK normalization fails because Cas12a has different cut profile
- in4mer 4-guide arrays without all-singleton controls: GI scoring requires single-gene baselines

## Cas9 vs Cas12a for Multiplex

| Property | Cas9 paired (Big Papi) | Cas12a multiplex (in4mer / Inzolia) |
|----------|------------------------|--------------------------------------|
| Multiplex capacity per cassette | 2 sgRNAs (paired) | 4 (in4mer); 2 (standard Cas12a) |
| sgRNA processing | U6 and H1 promoters driving sgRNAs for two orthologous Cas9s | Single transcript processed by Cas12a itself |
| sgRNA inhibition with multiple targets | None | None (Cas12a's intrinsic processing handles all) |
| Library size for 1,000 pairs | ~4,000-6,000 paired cassettes (4-6 per pair) | ~2,000 arrays (2 per pair) plus singleton controls |
| Validated libraries | Limited (mostly custom) | Inzolia: ~49k 4-guide arrays covering 19,687 genes plus ~4,435 paralog pairs |
| Per-perturbation editing efficiency | High (each sgRNA independently) | Variable (Cas12a less efficient on some targets) |
| Best for | Pairwise GI of specific interest | Genome-scale paralog buffering; multi-gene perturbation |

**Recommendation:** For modern paralog screens, use Cas12a multiplex with the Inzolia library. It is ~30% smaller than a typical monogenic Cas9 library while additionally covering ~4,000 paralog pairs (Esmaeili Anvar 2024), which makes it more cost-effective at genome scale.

## The Paralog Buffering Phenomenon

**Dede et al 2020 *Genome Biol* 21:262** showed that a large share of constitutively expressed genes are never scored as essential in any Cas9 single-KO fitness screen (3,032 of 7,282; 42%), and that these never-essentials are strongly enriched for paralogs. The reason: gene paralogs perform redundant essential functions. Loss of one paralog is buffered by the other; only loss of both creates the essentiality phenotype.

**Quantified impact:** 24 synthetic-lethal paralog pairs identified in Dede 2020 across 3 cell lines; 19 of 24 (79%) reproduce in >=2 lines, 14 of 24 (58%) in all 3. These pairs were not findable by single-gene Cas9 screens, requiring combinatorial methodology.

**Examples:**
- **MAPK1 (ERK2) + MAPK3 (ERK1):** ERK family redundancy in proliferation
- **PIK3CA + PIK3CB:** PI3K alpha/beta redundancy
- **AKT1 + AKT2:** AKT family redundancy
- **HSP90AA1 + HSP90AB1:** HSP90 alpha/beta redundancy
- **STAG1 + STAG2:** Cohesion complex paralogs

Each is buffered: loss of one is tolerated; loss of both is lethal.

## Genetic Interaction (GI) Scoring

**Goal:** Identify pairs where the double-knockout fitness differs from the additive expectation.

**Approach:** From per-pair and per-singleton fitness data, compute GI = observed_double_LFC - (single_A_LFC + single_B_LFC). Synthetic lethal: GI < threshold (more depleted than additive). Synthetic rescue: GI > threshold (less depleted than additive).

```python
import pandas as pd
import numpy as np
from scipy.stats import zscore

def gi_score(paired_lfc_df, single_lfc_df):
    '''Score genetic interactions from paired vs single LFCs.

    paired_lfc_df: rows = paired-KO; columns = ['gene_A', 'gene_B', 'paired_lfc']
    single_lfc_df: rows = single-KO; columns = ['gene', 'single_lfc']
    '''
    single = dict(zip(single_lfc_df['gene'], single_lfc_df['single_lfc']))
    df = paired_lfc_df.copy()
    df['single_A_lfc'] = df['gene_A'].map(single)
    df['single_B_lfc'] = df['gene_B'].map(single)
    df['expected_additive'] = df['single_A_lfc'] + df['single_B_lfc']
    df['gi_score'] = df['paired_lfc'] - df['expected_additive']
    df = df.dropna(subset=['gi_score'])          # a single missing singleton would NaN every z-score
    df['gi_z'] = zscore(df['gi_score'])
    df['gi_class'] = np.where(df['gi_z'] < -2, 'synthetic_lethal',
                                np.where(df['gi_z'] > 2, 'synthetic_rescue', 'no_interaction'))
    return df.sort_values('gi_z')
```

**Interpretation:**
- GI z-score < -2: Synthetic lethal (double-KO more lethal than expected) -- candidate drug target combinations
- GI z-score > 2: Synthetic rescue (double-KO less lethal than expected) -- compensatory pathway / paradoxical hit
- GI z-score -1 to 1: No interaction; effects are additive

## Run Combinatorial Screen Analysis (MAGeCK MLE with Interaction Indicator)

**Goal:** Use MAGeCK MLE to estimate the effect of each gene independently and the additional effect when both genes are simultaneously perturbed.

**Approach:** Design matrix encodes single-A, single-B, double-AB conditions; the `interaction` column is set to 1 only for double-KO samples. The resulting beta for that column captures the extra effect beyond the sum of single-gene betas. Note: MAGeCK MLE does not natively perform a formal interaction-significance test, but the `interaction|beta` and `|fdr` columns serve as the GI estimate; for formal interaction testing, compute GI = observed_double_lfc - (single_A_lfc + single_B_lfc) explicitly (see GI scoring section below).

```bash
# Design matrix encoding double-KO as a separate "interaction" indicator
# Conditions: NT (control), A_KO, B_KO, A_B_KO
cat > combo_design.txt <<EOF
Samples         baseline    geneA       geneB       interaction
NT_r1           1           0           0           0
NT_r2           1           0           0           0
A_r1            1           1           0           0
A_r2            1           1           0           0
B_r1            1           0           1           0
B_r2            1           0           1           0
AB_r1           1           1           1           1
AB_r2           1           1           1           1
EOF

mageck mle \
    --count-table combo_counts.txt \
    --design-matrix combo_design.txt \
    --output-prefix combo_mle

# Output: per-gene beta scores per design column
# The "interaction" column beta captures additional joint effect beyond additive
```

**Interpretation of MAGeCK MLE output:**

| Column | Meaning |
|--------|---------|
| `geneA|beta` | Single-A effect |
| `geneB|beta` | Single-B effect |
| `interaction|beta` | Additional effect under joint perturbation beyond sum of singles |
| `interaction|p-value`, `|fdr` | Significance vs zero |

A significantly negative `interaction|beta` is synthetic lethal; positive is synthetic rescue. For formal GI hypothesis testing, prefer the explicit GI scoring approach (next section) over MAGeCK MLE interpretation, since MAGeCK MLE does not validate the additive null.

## Inzolia / in4mer 4-Guide Array Analysis

**Esmaeili Anvar 2024 *Nat Commun* 15:3577** introduced in4mer, a Cas12a multiplex architecture where each array contains 4 guides processed by Cas12a's intrinsic crRNA-processing activity. The Inzolia library is the canonical implementation, covering the protein-coding genome plus ~4,435 paralog pairs.

**Library design:**
- 4 guides per cassette (Cas12a single-transcript array)
- Per pair: 2 arrays carrying 2 guides per gene, with the guides presented in different order across the two arrays
- Includes singleton controls: each single gene is covered by 2 four-guide arrays (4 guides per gene, order swapped)
- ~49,000 total arrays covering 19,687 genes, ~4,435 paralog pairs, 376 triples, and 100 quads

```python
# Per-pair analysis from in4mer screen
def in4mer_pair_analysis(paired_counts_df, gene_pairs, value_cols):
    '''Aggregate cassette-level counts to per-pair statistics.
    paired_counts_df: rows = cassettes, with a cassette_id COLUMN (reset_index first if it is the index).
    gene_pairs: DataFrame with cassette_id and gene_A, gene_B columns.
    value_cols: the numeric sample/LFC columns to aggregate.
    '''
    merged = paired_counts_df.merge(gene_pairs, on='cassette_id')
    return merged.groupby(['gene_A', 'gene_B'])[value_cols].agg(['mean', 'std', 'count'])
```

## Failure Modes

### Dual-sgRNA construct recombines in the lentiviral vector

**Trigger:** A dual-sgRNA construct built from repeated elements -- two copies of the U6 promoter, or two copies of the SpCas9 tracrRNA scaffold.
**Mechanism:** Najm 2018 reports that repetitive elements in lentiviral vectors, including the U6 promoter and multiple copies of the tracrRNA sequence, drive high levels of recombination and reduce combinatorial screen efficiency. Big Papi avoids this by pairing two orthologous enzymes (SaCas9 + SpCas9), whose scaffolds differ, and expressing the two sgRNAs from distinct U6 and H1 promoters.
**Symptom:** Constructs collapse to a single perturbation; measured GI scores are diluted toward zero.
**Fix:** Use the pPapi architecture (orthologous Cas9s, U6 + H1) rather than duplicated U6/tracr elements; verify construct integrity by amplicon sequencing of clones.

### Cas12a screen with low editing efficiency

**Trigger:** Cas12a less efficient than Cas9 at some loci; some guides in the 4-guide array don't cut.
**Mechanism:** Cas12a editing rate varies by sequence context; some loci edit at <30%.
**Symptom:** Specific pairs missing expected effects despite cassette presence.
**Fix:** Pilot Cas12a efficiency at the loci before full screen; use enCas12a (enhanced) variant; for known low-efficiency loci, supplement with Cas9.

### GI scoring without singletons

**Trigger:** Library lacks single-gene controls (only paired knockouts).
**Mechanism:** GI = paired - expected_additive requires single-gene LFC; without them, expected cannot be computed.
**Symptom:** Cannot score GI; only paired LFCs available.
**Fix:** Design library to include singletons (place gene A with 3 placeholder guides; gene B with 3 placeholders); re-run with full design.

### Single-gene LFCs from different cell line

**Trigger:** Using public single-gene LFCs (e.g., DepMap) as the baseline for paired-screen GI scoring.
**Mechanism:** Single-gene effects are cell-line specific; using HCT116 single-gene LFCs to score K562 paired-screen GIs is invalid.
**Symptom:** GI scores look noisy; many false positives.
**Fix:** Include singleton controls in the screen; or use cell-line-matched DepMap data.

### Confounding cell-cycle / proliferation in GI scoring

**Trigger:** Paired KO of two cell-cycle-impacting genes; the double-effect saturates cell cycle.
**Mechanism:** If A_KO causes 50% growth arrest and B_KO causes 50%, the combined 75% arrest is already saturating proliferation; additive expectation overestimates double-effect, generating false "synthetic-rescue."
**Symptom:** GI scores positive for pairs of essential cell-cycle genes; biologically unexpected.
**Fix:** Use log-space (LFC) GI scoring rather than linear; saturation is less severe in log-space. Alternative: model with logistic / saturable response curve.

### Library skew amplifying noise

**Trigger:** Inzolia library has uneven cassette representation; some pairs at 10x lower coverage than others.
**Mechanism:** Standard library QC (Gini, skew) applies; low-coverage cassettes yield noisier LFCs.
**Symptom:** GI z-scores vary 2-3x across cassettes targeting the same pair.
**Fix:** Standard library QC; for low-coverage pairs, aggregate fewer cassettes but with more sequencing depth; or drop low-coverage pairs from analysis.

## Cross-Modality Validation

For high-stakes synthetic-lethal hits (drug-target nomination), validate by:

1. **Orthogonal chemistry:** Re-validate with Cas9 if Cas12a, or vice versa
2. **Arrayed validation:** Single-knock-out arrayed setup with same cell line; quantify proliferation
3. **CRISPRi orthogonal:** Use dCas9-KRAB to confirm knockdown phenotype (no DNA damage)
4. **Pharmacological:** Inhibit paralog with drug; confirms target accessibility for drug development

## Quantitative Thresholds

| Threshold | Value | Source / Rationale |
|-----------|-------|--------------------|
| Synthetic lethal GI z-score | <-2 | Standard convention |
| Synthetic rescue GI z-score | >2 | Standard convention |
| No interaction | -1 to +1 | Within additive expectation |
| Cas9 paired-screen cassette count per pair | 4-6 | Standard library convention |
| Cas12a 4-guide arrays per paralog pair (Inzolia) | 2 (2 guides per gene, order swapped) | Esmaeili Anvar 2024 |
| Singletons in combinatorial library | At least 4-6 per single gene | For stable expected_additive |
| Cells per cassette for stable GI | 500+ at infection | Standard pooled-screen coverage |
| Cas12a editing efficiency for inclusion | >50% | Below = unreliable signal |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| Dual-sgRNA construct acts as single | Recombination between repeated U6/tracr elements | Use pPapi (orthologous SaCas9 + SpCas9, U6 + H1) |
| Cas12a low editing | Locus-specific inefficiency | Pilot loci first; use enCas12a |
| Cannot compute GI | No singletons in library | Re-design to include all-singletons |
| GI scores noisy | Library skew | Standard library QC; aggregate cassettes |
| Many false "rescue" GIs | Saturation in linear-space | Use log-space (LFC) GI scoring |
| Drug-target paralog shows no GI in screen | Cell-line-specific buffering | Cross-validate with multiple lines |

## References

- Najm FJ et al. 2018. *Nat Biotechnol* 36:179. Big Papi paired-Cas9 platform.
- DeWeirdt PC et al. 2021. *Nat Biotechnol* 39:94. enAsCas12a multiplex.
- Esmaeili Anvar N et al. 2024. *Nat Commun* 15:3577. in4mer / Inzolia paralog library.
- Dede M et al. 2020. *Genome Biol* 21:262. Paralog buffering in Cas9 screens.
- Thompson NA et al. 2021. *Nat Commun* 12:1302. Combinatorial CRISPR screen identifying paralog fitness effects.
- Boettcher M et al. 2018. *Nat Biotechnol* 36:170. Dual CRISPR activation + knockout directional genetic-interaction screen.
- Horlbeck MA et al. 2018. *Cell* 174:953-967. CRISPRi combinatorial genetic-interaction map; paralog buffering as a co-essentiality pattern was characterized more directly in Dede 2020 *Genome Biol* 21:262 and Gonatopoulos-Pournatzis 2020 *Nat Biotechnol* 38:638.

## Related Skills

- crispr-screens/library-design - Inzolia / in4mer / Big Papi library design
- crispr-screens/screen-qc - Library QC including cassette skew
- crispr-screens/mageck-analysis - MAGeCK MLE with interaction terms
- crispr-screens/hit-calling - Cross-method analysis of combinatorial data
- crispr-screens/perturb-seq-analysis - Combinatorial Perturb-seq
- crispr-screens/copy-number-correction - Pre-correction for cancer-line combinatorial screens
- crispr-screens/in-vivo-screens - In-vivo paralog screens
- pathway-analysis/go-enrichment - Functional analysis of GI clusters

## Usage Guide

# Combinatorial CRISPR Screens - Usage Guide

## Overview

Decision-grade design and analysis of combinatorial CRISPR screens. Covers paired-Cas9 (Big Papi, Najm 2018), enhanced AsCas12a multiplex (enCas12a, DeWeirdt 2021), in4mer 4-guide arrays (Esmaeili Anvar 2024), and Inzolia paralog library; paralog buffering detection (Dede 2020, Thompson 2021) for synthetic-lethal targets; genetic-interaction (GI) scoring; and the MAGeCK MLE interaction-term approach.

## Prerequisites

```bash
conda install -c bioconda mageck   # not on PyPI
pip install pandas numpy scipy matplotlib
# Inzolia library annotation: bioconductor or hart-lab
# Inzolia annotation: Nat Commun 15:3577 supplement, or Addgene #209551-2

# Cas12a-aware analysis tools
# No dedicated Cas12a helper package; use pandas/numpy with the library annotation
```

Required inputs:
- Cassette-level count matrix (rows = cassettes, columns = samples)
- Library annotation: cassette_id -> gene_A, gene_B (and gene_C, gene_D for in4mer)
- Singleton controls in library
- Vehicle / Day 0 / endpoint samples

## Quick Start

Tell the AI agent what to do:
- "Design an Inzolia paralog-pair library covering 600 paralog pairs in the kinase / transcription factor / DDR families with all-singleton controls"
- "Analyze my Cas12a multiplex paralog screen: compute per-pair GI scores; identify synthetic-lethal pairs at GI z-score <-2"
- "Compare Big Papi paired-Cas9 vs Inzolia Cas12a for the same paralog-pair set"
- "Diagnose: my paired-Cas9 cassettes seem to act as single perturbations -- diagnose dual-cassette cloning failure"
- "Run MAGeCK MLE with explicit interaction terms on my 4-condition combinatorial screen (NT, A_KO, B_KO, A_B_KO)"

## Example Prompts

### Library Design

> "Build an Inzolia-style enAsCas12a 4-guide array library covering 400 receptor tyrosine kinase paralog pairs. Include singletons (gene A alone, gene B alone, double-NTC) so we can compute GI = double_LFC - sum(single_LFC). Output library.tsv."

> "Design Big Papi constructs for 150 specific DDR pathway pairs using the pPapi architecture: SaCas9 sgRNA and SpCas9 sgRNA expressed from the U6 and H1 promoters, with SpCas9 supplied by the cell line. Verify by amplicon sequencing of clones."

### Per-Pair GI Analysis

> "Apply GI scoring to my paired-Cas9 screen. From paired_lfc.tsv and single_lfc.tsv, compute observed_double - (single_A + single_B). Z-normalize across pairs. Classify: SL (z <-2), rescue (z >2), no-interaction (otherwise)."

> "From my in4mer Inzolia screen counts, aggregate cassette-level LFCs by paralog pair. Compute per-pair GI z-scores. Identify 24+ synthetic-lethal pairs as in Dede 2020."

### MAGeCK MLE with Interactions

> "Build MAGeCK MLE design matrix for a 4-condition combinatorial screen: NT, A_KO, B_KO, A_B_KO. Include interaction column. Run mageck mle; output per-pair `interaction|beta` and `|fdr`. Flag synthetic-lethal pairs at FDR <0.05 with negative beta."

### Method Comparison

> "Compare GI z-scoring vs MAGeCK MLE interaction-term approach on the same screen. Investigate disagreement: which method is more sensitive for small-effect interactions?"

> "Validate Big Papi (Cas9) vs Inzolia (Cas12a) on the same 50 paralog pairs. Quantify concordance of synthetic-lethal calls."

### Diagnostics

> "My Cas12a in4mer screen has 20% of cassettes editing <50% per Cas12a editing assay. Investigate: locus-specific inefficiency? Filter and re-analyze."

> "Many GI z-scores are positive (synthetic rescue) for essential pairs (e.g., RPS3 + RPL11). Diagnose: linear-space saturation; switch to log-space (LFC) GI scoring."

> "My paired-Cas9 cassettes show as single perturbation despite design. Diagnose: recombination between repeated U6/tracrRNA elements; re-clone in pPapi (orthologous SaCas9 + SpCas9, U6 + H1); re-clone with validated dual-cassette protocol."

## What the Agent Will Do

1. Identify screen architecture: paired-Cas9 vs Cas12a multiplex vs in4mer
2. Verify library composition: paired cassettes + singletons + NTCs
3. Run standard pooled-screen counting and QC (see [[screen-qc]])
4. For Cas12a: verify per-locus editing efficiency >50%
5. Compute per-cassette LFCs vs control
6. Aggregate to per-pair LFCs across replicate cassettes
7. Extract single-gene LFCs from singleton-control cassettes
8. Compute GI = observed_double - expected_additive
9. Z-normalize GI across all pairs; apply z = -2 cutoff for synthetic lethal
10. Cross-validate via MAGeCK MLE interaction-term analysis
11. Annotate hits against COSMIC, paralog databases, and known synthetic-lethal pairs
12. Output: per-pair GI table, synthetic-lethal candidates, MAGeCK MLE comparison, validation strategy

## Tips

- For genome-scale paralog screens, Inzolia (Cas12a, 4-guide arrays) is preferred. It is ~30% smaller than a typical monogenic Cas9 library while additionally covering ~4,000 paralog pairs, which makes it more cost-effective at scale.
- Always include singleton controls in your library. Without them, you cannot compute GI; you only have paired LFCs without baseline.
- Per-gene per-pair, include 4+ cassettes for stable GI scoring. Single-cassette per pair gives noisy z-scores.
- Cas12a editing efficiency is locus-specific. Pilot at representative loci before screening; flag low-efficiency loci.
- For drug-target nomination, validate synthetic-lethal hits via:
  - Orthogonal chemistry (Cas9 if originally Cas12a)
  - Arrayed knock-out validation
  - CRISPRi orthogonal (no DNA damage)
  - Pharmacological inhibition with drugs
- Linear-space GI saturation: for essential-pair tests where both genes are independently essential, the additive expectation overestimates the saturable double-effect. Use log-space (LFC) GI scoring.
- For combinatorial Perturb-seq (single-cell readout of multi-perturbation), see [[perturb-seq-analysis]].
- Dual-sgRNA constructs with repeated U6/tracr elements recombine in lentivirus and collapse to a single perturbation. Use the pPapi architecture and verify by amplicon sequencing of clones. Verify by amplicon sequencing of clones before screening.

## Decision Cheat Sheet

| Goal | Architecture | Library |
|------|--------------|---------|
| Genome-scale paralog buffering | Cas12a multiplex | Inzolia (4-guide arrays) |
| Specific pairwise GI | Paired-Cas9 | Big Papi |
| 3-way / 4-way KO | Cas12a in4mer | Custom in4mer |
| Combinatorial Perturb-seq | Cas9 multi-cassette + scRNA | Custom |
| Drug + KO interaction | Standard library + drug | drugZ or MAGeCK MLE |

## Thresholds

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Synthetic lethal | GI z <-2 | Standard |
| Synthetic rescue | GI z >2 | Standard |
| Cassettes per pair | 4-6 | Stable GI |
| Singletons per gene | 4-6 cassettes | For expected_additive |
| Cas12a editing efficiency | >50% | Per-locus inclusion |
| Library coverage at infection | 500x cassettes/cells | Standard pooled |

## Related Skills

- crispr-screens/library-design - Inzolia / in4mer / Big Papi design
- crispr-screens/screen-qc - Cassette-level QC
- crispr-screens/mageck-analysis - MAGeCK MLE with interaction terms
- crispr-screens/hit-calling - Cross-method validation
- crispr-screens/perturb-seq-analysis - Combinatorial Perturb-seq
- crispr-screens/copy-number-correction - Pre-correction for cancer-line screens
- pathway-analysis/go-enrichment - Functional analysis of GI clusters

## Bundled Files

- `crispr-screens--combinatorial-screens--examples--gi_scoring.py` — copied from `examples/gi_scoring.py`
