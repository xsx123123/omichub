# bio-systems-biology-gene-essentiality

> Bundled component reference for `systems-biology/gene-essentiality` (original source: `skills/bio_skills/systems-biology/gene-essentiality`).

Performs in-silico single and double gene deletions, condition-dependent essentiality, and synthetic-lethality screens on genome-scale metabolic models with COBRApy, evaluating gene-protein-reaction rules and comparing FBA re-optimization against MOMA/ROOM minimal-adjustment. Use when predicting essential genes, finding synthetic-lethal pairs for drug targets, choosing a growth cutoff, deciding FBA vs MOMA vs ROOM for a knockout, making essentiality medium-specific to match an experiment, or validating predictions against Keio/Tn-seq/CRISPR screens with MCC.

## Instructions

## Version Compatibility

Reference examples tested with: COBRApy 0.29+, Python 3.10+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

Note: `single_gene_deletion` / `double_gene_deletion` spawn worker processes, so call them inside `if __name__ == '__main__':` (or pass `processes=1`) or a spawn platform will recurse. `delete_model_genes` is deprecated since 0.25; use `knock_out_model_genes` / `remove_genes`.

# Gene Essentiality Analysis

**"Which genes are essential for growth in my organism?"** -> Delete each gene (via its GPR rule), re-solve the model, and call a gene essential when its knockout drops predicted growth below a chosen cutoff - always relative to a specific model and medium.
- Python: `cobra.flux_analysis.single_gene_deletion()`, `double_gene_deletion()`, `moma()`, `room()` (COBRApy)

## The governing principle: essentiality is a model-and-medium prediction, not a gene property

An in-silico knockout answers "can THIS network still make biomass on THIS medium after this perturbation?" Everything else follows from taking that literally:

- A gene knockout is NOT a reaction knockout. Genes map to reactions through the gene-protein-reaction (GPR) rule: AND = protein complex (all subunits needed), OR = isozymes (any one suffices). A gene in an OR with a viable partner does nothing when deleted - isozyme masking is the dominant source of false non-essential calls and the reason synthetic lethals exist. Always delete GENES and let the GPR decide which reactions close; deleting reactions directly is a different, usually wrong, analysis.
- The essential/non-essential CUTOFF is a policy choice, not a library default. COBRApy returns raw knockout growth rates; there is no `growth_cutoff` argument. The cutoff (commonly <1-10% of wild type) moves the essential set in the "sick but alive" tail. It should be reported and swept (1/2/5/10%); genes whose call flips are low-confidence hypotheses.
- Essentiality is medium-dependent. Rich vs minimal media give different essential sets (a gene for a biosynthetic pathway is essential on minimal medium but dispensable when the product is supplied). To compare to an experiment, set the SAME medium the experiment used (LB vs M9), or the comparison is meaningless.
- Predictions have a ceiling (~85-93% accuracy on E. coli metabolic genes). False essentials come from a missing bypass/isozyme in the model; false non-essentials come from biology FBA cannot see (regulation, toxicity, essential non-metabolic or structural roles). Report MCC, not accuracy - essential genes are the minority class, so accuracy is inflated by the true-negative pile.

## Decision: which knockout method, which order

| Goal | Method | Assumption / when |
|------|--------|-------------------|
| Essential genes, evolved/adapted strain, or only hard lethality | FBA `single_gene_deletion` | mutant re-optimizes to max growth; cheapest; lethality calls agree with MOMA anyway |
| Immediate/fresh transposon or CRISPR mutant (one growth cycle) | MOMA `moma` | mutant stays closest in flux space to wild type (QP); fits fresh-mutant fluxes better |
| Fresh mutant where response is a few regulatory on/off switches | ROOM `room` | minimizes the NUMBER of significantly changed fluxes (MILP); recovers short bypasses |
| Synthetic-lethal PAIRS | `double_gene_deletion` on viable singles | both single KOs viable, double lethal; O(n^2), restrict the gene list |
| Higher-order lethal sets (triples/quads) | Fast-SL (flux-support pruning) | brute-force O(n^3+) infeasible; Fast-SL prunes by flux support |
| Condition/medium contrast | per-medium `single_gene_deletion` in `with model:` | essentiality re-computed under each defined medium |

MOMA/ROOM classify lethality similarly to FBA; they differ mainly on the quantitative growth of sick-but-alive mutants. Match the method to the timescale of the actual experiment.

## Single-Gene Deletion Screen

**Goal:** Rank every gene by the growth defect of its knockout and flag essential and growth-reducing genes.

**Approach:** Take wild-type growth once, then `single_gene_deletion` clamps each gene's reactions to zero through the GPR, re-optimizes, and returns a DataFrame with columns `ids` (a set holding the deleted gene id(s)), `growth`, and `status`. The caller applies the cutoff.

```python
import cobra
from cobra.flux_analysis import single_gene_deletion

model = cobra.io.load_model('textbook')
wt_growth = model.slim_optimize()

results = single_gene_deletion(model)          # DataFrame: ids (set of gene ids), growth, status
results['gene'] = results['ids'].apply(lambda s: list(s)[0])   # ids elements are gene-id STRINGS
results['relative'] = results['growth'] / wt_growth

ESSENTIAL_CUTOFF = 0.01                          # KO grows < 1% of WT -> essential (policy, not a default)
essential = results[results['relative'] < ESSENTIAL_CUTOFF]
print(f'Essential genes: {len(essential)} / {len(model.genes)} on this medium')
```

## Classify with a threshold sweep (report low-confidence calls)

```python
def classify_essentiality(results, wt_growth, cutoffs=(0.01, 0.02, 0.05, 0.10)):
    '''Classify genes and report how many calls flip across cutoffs (the sick-tail sensitivity).'''
    rel = results['growth'] / wt_growth
    calls = {c: set(results.loc[rel < c, 'gene']) for c in cutoffs}
    core = set.intersection(*calls.values())     # essential at every cutoff -> high confidence
    boundary = set.union(*calls.values()) - core # call depends on the cutoff -> low confidence
    return core, boundary
```

## MOMA / ROOM: the immediate, non-re-optimized mutant

```python
from cobra.flux_analysis import moma, room

# FBA assumes the mutant re-optimizes; a fresh knockout has not re-wired its regulation yet.
# MOMA keeps mutant flux closest (Euclidean) to wild type; ROOM minimizes the count of changed
# fluxes. Both need a wild-type reference solution and a QP/MILP-capable solver.
from cobra.util.solver import linear_reaction_coefficients
biomass = list(linear_reaction_coefficients(model))[0]   # the objective (biomass) reaction
wt = model.optimize()
with model:
    model.genes.get_by_id('b2276').knock_out()   # context-aware; reverts on block exit
    moma_sol = moma(model, solution=wt, linear=True)      # linear=True = fast LP approximation (lMOMA)
    # moma_sol.objective_value is the MINIMIZED ADJUSTMENT, not growth; read the biomass flux.
    print('MOMA mutant growth:', moma_sol.fluxes[biomass.id])
```

## Synthetic Lethality (double deletions + epistasis)

**Goal:** Find gene PAIRS that are viable singly but lethal together - redundant pathways and isozymes, and candidate combination drug targets.

**Approach:** Restrict to genes whose single knockout is viable (a synthetic lethal requires both singles viable), run pairwise `double_gene_deletion`, and keep pairs whose double-KO growth falls below the cutoff. Cost is O(n^2), so subset the gene list. Score interactions against the multiplicative neutral expectation (independent effects on an exponential growth rate).

```python
from cobra.flux_analysis import double_gene_deletion

viable = list(results.loc[results['relative'] > ESSENTIAL_CUTOFF, 'gene'])[:60]   # cap the O(n^2) sweep
dbl = double_gene_deletion(model, gene_list1=viable, gene_list2=viable)
dbl['n'] = dbl['ids'].apply(len)
sl_pairs = dbl[(dbl['n'] == 2) & (dbl['growth'] / wt_growth < ESSENTIAL_CUTOFF)]
print(f'Synthetic-lethal pairs: {len(sl_pairs)}')
# Genome-scale and higher-order (triple/quad) sets: use Fast-SL flux-support pruning (Pratapa 2015),
# not brute force.
```

## Condition-Specific Essentiality (match the experiment's medium)

**Goal:** Compare essential-gene sets across defined media to separate core-essential genes from condition-specific ones.

**Approach:** Apply each medium inside a `with model:` block (so it reverts), run the deletion screen, and take intersections/differences of the essential sets. Define media with real functions, not lambdas (a lambda cannot contain an assignment).

```python
def aerobic(m):
    m.reactions.EX_o2_e.lower_bound = -20

def anaerobic(m):
    m.reactions.EX_o2_e.lower_bound = 0

def essential_set(model, setup):
    with model:
        setup(model)
        wt = model.slim_optimize()
        res = single_gene_deletion(model)
        return set(res.loc[res['growth'] / wt < ESSENTIAL_CUTOFF, 'ids'].apply(lambda s: list(s)[0]))

sets = {name: essential_set(model, fn) for name, fn in [('aerobic', aerobic), ('anaerobic', anaerobic)]}
core = set.intersection(*sets.values())
condition_specific = {k: v - core for k, v in sets.items()}
```

## Validate against experiment (MCC, matched medium)

```python
# Compare predicted essentials to an experimental set (Keio single-KO, Tn-seq, or CRISPR fitness),
# on the SAME medium. Use MCC, not accuracy: essential genes are a minority class, so accuracy is
# inflated by the large true-negative pile.
from sklearn.metrics import matthews_corrcoef

def score(predicted_essential, experimental_essential, all_genes):
    y_pred = [g in predicted_essential for g in all_genes]
    y_true = [g in experimental_essential for g in all_genes]
    return matthews_corrcoef(y_true, y_pred)
```

## Common Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| Central gene predicted non-essential | it has an isozyme (OR in the GPR) that stays open | expected; that gene is a synthetic-lethal candidate, not truly dispensable |
| Deleting a reaction gives different results than deleting its gene | reaction KO ignores GPR; a gene may map to several reactions or share them | delete GENES (`single_gene_deletion` / `gene.knock_out()`), not reactions |
| `TypeError: 'set' object ... .id` | `ids` column holds sets of gene-id STRINGS, not gene objects | `list(s)[0]` gives the id string directly; no `.id` |
| Essential set disagrees with the paper | medium mismatch (LB vs M9) or a different cutoff | set the experiment's medium; report and sweep the cutoff |
| Script recurses / spawns endlessly | deletion functions parallelize; no `__main__` guard | wrap in `if __name__ == '__main__':` or pass `processes=1` |
| `AttributeError: delete_model_genes` | deprecated since cobra 0.25 | use `knock_out_model_genes` / `remove_genes`, or `gene.knock_out()` |
| High accuracy but poor agreement on real essentials | accuracy inflated by true negatives (minority class) | report MCC and sensitivity, not accuracy |

## Related Skills

- systems-biology/flux-balance-analysis - The FBA/medium/objective foundation these knockouts rest on
- systems-biology/model-curation - Missing isozymes/bypasses cause false essentials; curate before trusting calls
- systems-biology/strain-design - Growth-coupling designs build on knockout logic
- crispr-screens/hit-calling - Experimental essentiality screens to validate predictions
- pathway-analysis/go-enrichment - Functional enrichment of predicted essential-gene sets

## References

- Orth JD, Thiele I, Palsson BO. 2010. What is flux balance analysis? *Nat Biotechnol* 28(3):245-248.
- Segre D, Vitkup D, Church GM. 2002. Analysis of optimality in natural and perturbed metabolic networks. *PNAS* 99(23):15112-15117. (MOMA)
- Shlomi T, Berkman O, Ruppin E. 2005. Regulatory on/off minimization of metabolic flux changes after genetic perturbations. *PNAS* 102(21):7695-7700. (ROOM)
- Segre D, DeLuna A, Church GM, Kishony R. 2005. Modular epistasis in yeast metabolism. *Nat Genet* 37(1):77-83. (epistasis scoring, multiplicative expectation)
- Pratapa A, Balachandran S, Raman K. 2015. Fast-SL: an efficient algorithm to identify synthetic lethal sets in metabolic networks. *Bioinformatics* 31(20):3299-3305.
- Baba T, Ara T, Hasegawa M, et al. 2006. Construction of Escherichia coli K-12 in-frame, single-gene knockout mutants: the Keio collection. *Mol Syst Biol* 2:2006.0008.
- Monk JM, Lloyd CJ, Brunk E, et al. 2017. iML1515, a knowledgebase that computes Escherichia coli traits. *Nat Biotechnol* 35(10):904-908.

## Usage Guide

# Gene Essentiality Analysis - Usage Guide

## Overview

In-silico gene essentiality predicts which genes a metabolic model cannot lose and still make biomass. The result is a conditional prediction about a specific model on a specific medium, never an intrinsic property of a gene. Three choices dominate the outcome: the growth cutoff that separates essential from viable (a policy you set, not a library default), the medium (rich vs minimal give different essential sets), and the deletion method (FBA re-optimizes the mutant, MOMA/ROOM model an immediate un-adapted mutant). Because genes reach reactions through gene-protein-reaction rules, a gene with an isozyme partner looks non-essential no matter how central its reaction - which is exactly why synthetic-lethal pairs exist. Predictions top out around 85-93% accuracy on E. coli metabolic genes; report MCC, not accuracy, and match the medium when validating against experimental screens.

## Prerequisites

```bash
pip install cobra pandas scikit-learn
# QP/MILP methods (MOMA, ROOM) benefit from an academic CPLEX or Gurobi; HiGHS also works.
```

Inputs: a genome-scale model (SBML/JSON or a built-in like `load_model('textbook')`) and, for validation, an experimental essential-gene list (Keio, Tn-seq, or CRISPR fitness) with the medium it was measured on.

## Quick Start

Tell your AI agent:
- "Find the essential genes in my model on glucose minimal medium"
- "Sweep the essentiality cutoff and tell me which calls are low-confidence"
- "Use MOMA instead of FBA because these are fresh transposon mutants"
- "Find synthetic-lethal gene pairs among the viable genes"
- "Compare my predicted essentials to the Keio set and report the MCC"

## Example Prompts

### Essential Genes
> "Run single-gene deletions on iML1515 in M9 glucose, call genes essential below 1% of wild-type growth, and also report how many calls change if I use 5% instead."

### Method Choice
> "These are freshly knocked-out CRISPR mutants scored in one growth cycle - use MOMA, not FBA, and explain how the essential set differs from the FBA call."

### Synthetic Lethality
> "Among genes that are individually non-essential, find synthetic-lethal pairs and flag any that could be combination drug targets."

### Condition-Specific
> "Compare essential genes aerobically vs anaerobically and separate the core-essential set from the condition-specific ones."

### Validation
> "Compare my model's predicted essential genes to the Keio collection on the same medium and report MCC, sensitivity, and the false-essential and false-non-essential genes."

## What the Agent Will Do

1. Load the model and confirm the medium matches the intended condition (or the experiment being compared to).
2. Take wild-type growth, then run `single_gene_deletion` (GPR-aware) and apply an explicit cutoff.
3. Sweep the cutoff to separate high-confidence essentials from sick-tail, cutoff-dependent calls.
4. For fresh mutants, use MOMA/ROOM against a wild-type reference instead of FBA.
5. For synthetic lethality, restrict to viable singles and run `double_gene_deletion`; use Fast-SL logic for higher-order sets.
6. Recompute essentiality per medium for condition contrasts.
7. Validate against experimental screens on the matched medium and report MCC.

## Tips

- Delete genes, not reactions - `single_gene_deletion` evaluates the GPR so complexes and isozymes are handled correctly.
- The `ids` column holds sets of gene-id strings; `list(s)[0]` gives the id (no `.id` attribute).
- State and sweep the cutoff. A result that flips between a 1% and 5% cutoff is a threshold artifact, not a finding.
- Match the medium to the experiment before comparing; a biosynthesis gene is essential on minimal medium and dispensable on rich.
- Use MOMA/ROOM for immediate/un-evolved mutants and FBA for evolved strains or when only hard lethality matters (the methods mostly agree on lethal-vs-viable).
- Cap the double-deletion gene list; the sweep is O(n^2). Use Fast-SL flux-support pruning for triples/quads.
- A central gene that comes back non-essential almost always has an isozyme - treat it as a synthetic-lethal candidate.
- False essentials usually mean the model is missing a bypass or isozyme (a curation problem); false non-essentials mean the real killer is non-metabolic (regulation, toxicity) and FBA cannot see it.
- Report MCC and sensitivity, not accuracy; essential genes are the minority class and accuracy is inflated by true negatives.
- Wrap deletion scripts in `if __name__ == '__main__':` (the functions spawn workers) or pass `processes=1`.

## Related Skills

- systems-biology/flux-balance-analysis - The FBA/medium/objective foundation for knockouts
- systems-biology/model-curation - Fix missing isozymes/bypasses that cause false essentials
- systems-biology/strain-design - Growth-coupling designs that build on knockout logic
- crispr-screens/hit-calling - Experimental essentiality screens for validation
- pathway-analysis/go-enrichment - Functional enrichment of essential-gene sets

## Bundled Files

- `systems-biology--gene-essentiality--examples--gene_essentiality.py` — copied from `examples/gene_essentiality.py`
