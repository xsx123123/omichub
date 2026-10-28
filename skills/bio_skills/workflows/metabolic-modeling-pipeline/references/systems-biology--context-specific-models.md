# bio-systems-biology-context-specific-models

> Bundled component reference for `systems-biology/context-specific-models` (original source: `skills/bio_skills/systems-biology/context-specific-models`).

Builds tissue-, cell-type-, and condition-specific metabolic models by integrating transcriptomic or proteomic data into a generic genome-scale model, using extraction algorithms (GIMME, iMAT, INIT/tINIT, MADE, E-Flux, CORDA, FASTCORE) via troppo and corda in Python or the COBRA Toolbox/RAVEN in MATLAB. Use when pruning a generic model to a context, choosing an extraction method and expression threshold, mapping expression through GPR rules to reactions, deciding whether an objective is required (GIMME vs iMAT), avoiding the growth-objective trap for non-proliferating tissue, or judging how much of a context-specific model is real signal versus an artifact of the threshold and method.

## Instructions

## Version Compatibility

Reference examples tested with: COBRApy 0.29+, corda 0.5+, numpy 1.26+, pandas 2.2+, Python 3.10+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

Note: COBRApy core does NOT implement GIMME/iMAT/INIT. Real Python implementations live in `troppo` (multi-method) and `corda` (CORDA); the reference multi-method implementations are the MATLAB COBRA Toolbox `createTissueSpecificModel` and RAVEN (INIT/tINIT). Do not expect a `cobra.flux_analysis.gimme()`; it does not exist.

# Context-Specific Models

**"Build a liver-specific metabolic model from my expression data"** -> Prune/constrain a generic genome-scale model to the reactions an extraction algorithm judges active in that context, given omics data mapped through GPR rules and a threshold.
- Python: `corda.CORDA` (CORDA), `troppo` (GIMME/iMAT/tINIT/FASTCORE/CORDA); MATLAB: COBRA Toolbox `createTissueSpecificModel`, RAVEN (COBRApy for downstream FBA)

## The governing principle: the threshold and method are the experiment, not the data

Two facts govern every context-specific model:

- Expression is NOT flux. A highly transcribed gene need not carry high flux (post-transcriptional regulation, allostery, kinetics decouple mRNA from enzyme activity), and an absent transcript does not prove its reaction is off. Absence is a moderately strong constraint; presence is a weak one. mRNA -> enzyme -> flux is a lossy chain, and every extraction method encodes a DIFFERENT guess about that chain.
- Method choice and thresholding dominate the result more than the biology does. Systematic evaluations found that no extraction method reliably beats the others, and that expression-integration methods often fail to beat parsimonious FBA, which uses NO expression at all; the choice of method x threshold x objective changes the model content MORE than the input data does (Machado & Herrgard 2014; Opdam 2017; Richelle 2019). The single on/off threshold is the highest-leverage hidden decision. Consequence: report the method, the threshold strategy, and the objective as first-class methods, and treat a reaction whose inclusion flips with a plausible threshold change as a hypothesis, not a finding.

A corollary trap: GIMME-family methods require a protected objective (usually biomass). For a differentiated, non-proliferating tissue (hepatocyte, neuron), forcing a growth objective is a category error - those cells are not making copies of themselves. Use an objective-free method (iMAT) or a task-based one (tINIT) for non-growing tissue, or define a genuine maintenance/functional task instead of biomass.

## Decision: which extraction method

| Method | Objective/task required? | Expression handling | Best implementation | When |
|--------|--------------------------|---------------------|---------------------|------|
| GIMME (Becker & Palsson 2008) | Yes (biomass/task) | discrete threshold; penalize below-threshold flux | troppo (Py); COBRA Toolbox (MATLAB) | proliferating cells with a real objective |
| iMAT (Shlomi 2008; Zur 2010) | No | discrete high/low buckets (MILP) | troppo (Py); COBRA Toolbox (MATLAB) | non-growing human tissue; the common default |
| INIT / tINIT (Agren 2012/2014) | tINIT: metabolic TASKS | protein/HPA evidence + net accumulation | RAVEN (MATLAB) | task-guaranteed, functional tissue models |
| MADE (Jensen & Papin 2011) | No | differential significance, no absolute threshold; needs >=2 conditions | MATLAB (TIGER) | comparative/time-course designs |
| E-Flux (Colijn 2009) | No | expression sets continuous flux BOUNDS (no discretization) | custom (simple) | quick continuous constraint; no on/off decision |
| CORDA (Schultz & Qutub 2016) | No | 5 confidence classes; dependency-rescued | corda (Python, turnkey) | cancer/tissue models; "concise not minimal" |
| FASTCORE (Vlassis 2014) | core reaction set | core + minimal consistent extension | troppo (Py); COBRA Toolbox | fast, compact, given a trusted core |

Honest tooling reality: the most complete, best-validated implementations are MATLAB (COBRA Toolbox / RAVEN). In Python, `troppo` is the multi-method option and `corda` is the most turnkey native implementation. Steering a user to "just use COBRApy" for iMAT/GIMME sends them into reimplementing an algorithm.

## Map Expression Through GPR Rules

**Goal:** Convert per-gene expression into a per-reaction activity score that respects enzyme logic.

**Approach:** Evaluate the GPR with min for AND (a complex is limited by its scarcest subunit) and max for OR (any isozyme suffices). This min/max convention is standard but lossy - it discards the quantitative contribution of all but the limiting/dominant gene.

```python
def reaction_activity(rxn, gene_expr, default=0.0):
    '''Aggregate gene expression to a reaction score: min over AND (complex), max over OR (isozyme).'''
    if not rxn.genes:
        return default
    values = [gene_expr.get(g.id, default) for g in rxn.genes]
    return max(values)   # simplified OR; a full parser applies min within each AND-clause first
```

## CORDA in Python (a real, turnkey extraction method)

**Goal:** Reconstruct a context-specific model that keeps as many high-confidence reactions as possible while excluding absent ones, rescuing reactions that high-confidence ones depend on.

**Approach:** Translate expression into CORDA's five confidence classes (-1 absent, 0 unknown, 1 low, 2 medium, 3 high) via the GPR, then let CORDA build a "concise but not minimal" model.

```python
from corda import CORDA, reaction_confidence

# gene_conf maps gene id -> confidence in {-1, 0, 1, 2, 3}; derive it from expression quantiles.
gene_conf = {g.id: 2 for g in model.genes}
rxn_conf = {r.id: reaction_confidence(r, gene_conf) for r in model.reactions}   # pass the Reaction, not its GPR string

opt = CORDA(model, rxn_conf)
opt.build()
context_model = opt.cobra_model('liver')   # verify the exact accessor for the installed corda version
```

## Conceptual GIMME-Style Constraint (illustration only)

**Goal:** Show the objective-protected pruning idea GIMME encodes, for teaching - not as a substitute for a validated implementation.

**Approach:** Require the objective to stay above a floor, then penalize/limit flux through reactions whose genes are all below the expression threshold. A faithful GIMME solves a single LP with an inconsistency score; this stub only illustrates the shape and must not be reported as GIMME output.

```python
import numpy as np

def gimme_style_stub(model, gene_expr, low_quantile=0.25, growth_floor=0.1):
    '''Illustrative only. For real GIMME/iMAT use troppo or the COBRA Toolbox.'''
    cutoff = np.quantile(list(gene_expr.values()), low_quantile)
    low = {g for g, v in gene_expr.items() if v < cutoff}
    ctx = model.copy()
    biomass = str(model.objective.expression).split('*')[1].split()[0]
    ctx.reactions.get_by_id(biomass).lower_bound = growth_floor   # protect the objective
    for rxn in ctx.reactions:
        genes = {g.id for g in rxn.genes}
        if genes and genes <= low:
            rxn.bounds = (max(rxn.lower_bound, -1.0), min(rxn.upper_bound, 1.0))
    return ctx
```

## Thresholding: the make-or-break decision

```python
# The single on/off threshold moves the model more than the algorithm does. Options:
#  - Global: one cutoff across all genes/samples (simple; ignores gene-specific expression ranges).
#  - Local: a per-gene cutoff (e.g. a gene is "on" relative to its own distribution across samples).
#  - StanDep (Joshi 2020): clusters genes by expression pattern and thresholds per cluster; captures
#    housekeeping vs peaky genes that a single global cutoff mishandles.
# Always run a sensitivity check: rebuild at 2-3 thresholds and report which reactions/pathways are
# stable vs threshold-dependent. Report proteomics-derived scores separately; protein is closer to
# flux capacity than mRNA but still not flux.
#  - Single-cell input: scRNA-seq zeros are dominated by technical DROPOUT, which inverts the
#    "absence is a strong constraint" logic (a zero may be an unobserved, not an absent, transcript).
#    Aggregate to pseudobulk or metacells PER CELL TYPE before extraction (or use a single-cell-native
#    method); do not threshold individual cells. See single-cell/cell-annotation.
```

## Common Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `AttributeError: cobra.flux_analysis has no gimme` | COBRApy ships no GIMME/iMAT/INIT | use troppo/corda (Python) or COBRA Toolbox/RAVEN (MATLAB) |
| Context model of a neuron/hepatocyte cannot satisfy biomass | GIMME-family objective forced on non-proliferating tissue | use iMAT (objective-free) or tINIT (task-based); do not protect biomass |
| Two analysts get different tissue models from the same data | threshold/method/objective differ | fix and report all three; run a threshold sensitivity sweep |
| Reaction present in data but pruned out | presence is a weak signal; the method judged it inactive in context | expected; do not over-trust presence, and check the GPR aggregation |
| Absent transcript but reaction kept | absence is only a moderate constraint; a dependency rescued it (CORDA) | inspect `opt.redundancies`/dependency rescue; decide if the rescue is justified |
| Model predicts overflow/Warburg poorly | expression pruning has no enzyme-capacity budget | use enzyme-constrained models (GECKO/sMOMENT) with proteomics |

## Related Skills

- systems-biology/flux-balance-analysis - Run FBA/FVA on the extracted context model
- systems-biology/gene-essentiality - Context-specific essentiality on the tissue model
- systems-biology/metabolic-reconstruction - The generic model these methods prune
- differential-expression/de-results - Expression input (bulk) for extraction
- single-cell/cell-annotation - Cell-type expression for cell-type-specific models

## References

- Becker SA, Palsson BO. 2008. Context-specific metabolic networks are consistent with experiments. *PLoS Comput Biol* 4(5):e1000082. (GIMME)
- Shlomi T, Cabili MN, Herrgard MJ, Palsson BO, Ruppin E. 2008. Network-based prediction of human tissue-specific metabolism. *Nat Biotechnol* 26(9):1003-1010. (iMAT method)
- Zur H, Ruppin E, Shlomi T. 2010. iMAT: an integrative metabolic analysis tool. *Bioinformatics* 26(24):3140-3142.
- Colijn C, Brandes A, Zucker J, et al. 2009. Interpreting expression data with metabolic flux models. *PLoS Comput Biol* 5(8):e1000489. (E-Flux)
- Jensen PA, Papin JA. 2011. Functional integration of a metabolic network model and expression data without arbitrary thresholding. *Bioinformatics* 27(4):541-547. (MADE)
- Agren R, Bordel S, Mardinoglu A, et al. 2012. Reconstruction of genome-scale active metabolic networks for 69 human cell types using INIT. *PLoS Comput Biol* 8(5):e1002518. (INIT; tINIT: Agren 2014 *Mol Syst Biol* 10:721)
- Schultz A, Qutub AA. 2016. Reconstruction of tissue-specific metabolic networks using CORDA. *PLoS Comput Biol* 12(3):e1004808. (CORDA)
- Vlassis N, Pacheco MP, Sauter T. 2014. Fast reconstruction of compact context-specific metabolic network models. *PLoS Comput Biol* 10(1):e1003424. (FASTCORE)
- Machado D, Herrgard M. 2014. Systematic evaluation of methods for integration of transcriptomic data into constraint-based models of metabolism. *PLoS Comput Biol* 10(4):e1003580.
- Opdam S, Richelle A, Kellman B, et al. 2017. A systematic evaluation of methods for tailoring genome-scale metabolic models. *Cell Syst* 4(3):318-329.
- Richelle A, Joshi C, Lewis NE. 2019. Assessing key decisions for transcriptomic data integration in biochemical networks. *PLoS Comput Biol* 15(7):e1007185.
- Joshi CJ, Schinn SM, Richelle A, et al. 2020. StanDep: capturing transcriptomic variability improves context-specific metabolic models. *PLoS Comput Biol* 16(5):e1007764.

## Usage Guide

# Context-Specific Models - Usage Guide

## Overview

A context-specific model prunes a generic genome-scale model down to the metabolism active in a particular tissue, cell type, or condition, by integrating transcriptomic or proteomic data. The uncomfortable truth to internalize first: the extraction method, the on/off threshold, and (for some methods) the protected objective shape the resulting model more than the input data does. Systematic evaluations found no method reliably beats the others, and mRNA is a weak, sometimes sign-wrong proxy for flux. So a context-specific model is largely an artifact of analyst choices, and those choices - method, threshold strategy, objective - must be reported as first-class methods and stress-tested. COBRApy does not implement these algorithms; the real Python options are troppo and corda, and the reference multi-method implementations are the MATLAB COBRA Toolbox and RAVEN.

## Prerequisites

```bash
pip install cobra numpy pandas
pip install corda           # turnkey native-Python CORDA
# troppo (github.com/BioSystemsUM/troppo) for GIMME/iMAT/tINIT/FASTCORE in Python
# For iMAT/GIMME/INIT with the most validated implementation: MATLAB COBRA Toolbox / RAVEN
```

Inputs: a generic genome-scale model (e.g. Recon3D/Human1 for human, or a bacterial GEM) and expression data (bulk RNA-seq TPM, microarray, or proteomics) with gene IDs that match the model. For MADE, at least two conditions.

## Quick Start

Tell your AI agent:
- "Build a liver-specific model from my GTEx expression, and tell me which method fits non-growing tissue"
- "Use CORDA in Python to extract a context model from my confidence classes"
- "Map my TPM through the GPR rules to reaction activity scores"
- "Rebuild the model at three thresholds and show me which reactions are threshold-dependent"
- "Which extraction method needs an objective and which does not?"

## Example Prompts

### Method Choice
> "I have hepatocyte RNA-seq. Recommend an extraction method given hepatocytes do not proliferate, and explain why forcing a biomass objective would be wrong here."

### Threshold Sensitivity
> "Extract a context model at the 10th, 25th, and 50th expression percentile and report which pathways are stable versus which appear or vanish with the threshold."

### CORDA in Python
> "Translate my expression into CORDA confidence classes through the GPR and build a context-specific model with corda."

### GPR Mapping
> "Aggregate my per-gene expression to per-reaction activity using min-for-AND and max-for-OR, and flag reactions where the aggregation is ambiguous."

## What the Agent Will Do

1. Load the generic model and confirm gene IDs match the expression data namespace.
2. Choose an extraction method from the decision table (objective-required vs not, task-based, differential).
3. Map expression through the GPR (min for AND, max for OR) into reaction activity or confidence classes.
4. Pick and justify a threshold strategy (global/local/StanDep), then extract with troppo/corda (Python) or COBRA Toolbox/RAVEN (MATLAB).
5. Rebuild at 2-3 thresholds and report stable vs threshold-dependent content.
6. Hand the extracted model to FBA/essentiality, noting that pruning has no enzyme-capacity budget.

## Tips

- Expression is not flux: presence is a weak signal, absence a moderate one; never report a pruned/kept reaction as biological fact without a sensitivity check.
- The threshold is the highest-leverage decision. Sweep it and report which reactions flip; a pathway that appears only at one cutoff is a threshold artifact.
- Match method to biology: GIMME needs an objective (wrong for non-proliferating tissue); iMAT is objective-free; tINIT uses metabolic tasks; MADE needs >=2 conditions.
- Do not force biomass on a hepatocyte or neuron - define a maintenance/functional task or use an objective-free method.
- Use min-for-AND/max-for-OR to aggregate GPRs, but remember it discards all but the limiting/dominant gene's quantitative value.
- COBRApy has no `gimme()`/`imat()`; use troppo or corda in Python, or the COBRA Toolbox/RAVEN in MATLAB - the MATLAB implementations are the most validated.
- Proteomics is closer to flux capacity than mRNA but still not flux; for capacity effects (overflow/Warburg) use enzyme-constrained models (GECKO/sMOMENT).
- For single-cell input, scRNA-seq zeros are mostly technical dropout, which breaks the "absence is a strong constraint" assumption; aggregate to pseudobulk or metacells per cell type before extraction rather than thresholding individual cells.
- Report method, threshold strategy, and objective together; two analysts with different choices will get different tissue models from identical data.

## Related Skills

- systems-biology/flux-balance-analysis - Run FBA/FVA on the extracted context model
- systems-biology/gene-essentiality - Context-specific essentiality on the tissue model
- systems-biology/metabolic-reconstruction - The generic model these methods prune
- differential-expression/de-results - Bulk expression input for extraction
- single-cell/cell-annotation - Cell-type expression for cell-type-specific models

## Bundled Files

- `systems-biology--context-specific-models--examples--context_specific.py` — copied from `examples/context_specific.py`
