# bio-genome-annotation-eukaryotic-gene-prediction

> Bundled component reference for `genome-annotation/eukaryotic-gene-prediction` (original source: `skills/bio_skills/genome-annotation/eukaryotic-gene-prediction`).

Predicts protein-coding gene structures (exons, introns, UTRs) in eukaryotic genomes with BRAKER3 (RNA-seq + protein evidence), BRAKER1/BRAKER2, GALBA (protein-only), Funannotate (fungi), GeMoMa (homology projection), or Helixer/Tiberius (deep-learning ab initio). Covers the evidence-first tool decision, mandatory soft-masking, the training-set-quality-dominates principle, OrthoDB clade-partition selection, the one-isoform-per-locus and missing-UTR traps, merge/split errors, and reference bias against orphan genes. Use when annotating a newly assembled eukaryotic genome, choosing a gene-prediction pipeline based on available evidence, or diagnosing a poor annotation.

## Instructions

## Version Compatibility

Reference examples tested with: BRAKER 3.0+, GALBA 1.0.11+, AUGUSTUS 3.5+, Funannotate 1.8+, HISAT2 2.2.1+, STAR 2.7.11+, BUSCO 5.5+, samtools 1.19+, gffutils 0.12+.

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags
- Python: `pip show <package>` then `help(module.function)` to check signatures

Reproducibility is engineered, not assumed: run BRAKER/GALBA/Funannotate from their official containers, and pin the **OrthoDB partition version** (v11 vs v12 give different hints -> different models), the repeat library, and the Dfam release. GeneMark (inside BRAKER) historically required an expiring academic `.gm_key`; the requirement has relaxed in recent versions but check the installed version's docs. If code throws an error, introspect the installed tool and adapt rather than retrying.

# Eukaryotic Gene Prediction

**"Predict genes in my eukaryotic genome"** -> Identify protein-coding gene structures from a soft-masked assembly using RNA-seq and/or protein evidence to train and guide a gene finder.
- CLI: `braker.pl --genome=masked.fa --prot_seq=orthodb_clade.fa --rnaseq_sets_ids=SRR... --softmasking` (BRAKER3)

## The Single Most Important Modern Insight -- Training-Set Quality and Evidence Dominate, Not the Algorithm

Gene-prediction accuracy is governed by the quality of the **training set** and the **extrinsic evidence**, not by which gene-finder is chosen. A 2024-era HMM (AUGUSTUS) trained on a clean, evidence-validated gene set beats a fancier model trained on garbage. This reframes every decision:

- BRAKER3's accuracy jump is **not** a better HMM and **not** the TSEBRA combiner (the common misattribution). It is GeneMark-ETP's method of mining a **high-confidence training set** from loci where RNA-seq-assembled transcripts AND protein homology independently agree, then training AUGUSTUS on that (Brůna 2024 *Genome Res* 34:757; Gabriel 2024 *Genome Res* 34:769). BRAKER3 beats BRAKER1/2 because it learns from loci it has two reasons to trust.
- Therefore the **first** question is "what evidence do I have, and is it from the right clade?" - not "which tool?" Soft-masking and OrthoDB-partition choice are upstream of, and more consequential than, the predictor.
- **The #1 silent killer is training on a bad assembly.** A finder trained on a contaminated, fragmented, or repeat-polluted assembly produces confidently wrong models *genome-wide* that are syntactically valid, BUSCO-complete, and undetectable from the GFF3. Decontaminate and check assembly contiguity/BUSCO **before** any self-trainer touches the genome.
- The 2025-2026 deep-learning twist: Tiberius/Helixer can match BRAKER3's evidence-based accuracy with **no evidence at all** on well-represented clades (vertebrates) - but they degrade on under-represented lineages and are isoform/UTR-naive. The field is mid-transition; do not present DL as universally superior.

## Tool Taxonomy

| Pipeline | Citation | Evidence used | When |
|----------|----------|---------------|------|
| BRAKER3 | Gabriel 2024 *Genome Res* | RNA-seq + protein (OrthoDB) | **Default when both exist**; HC-training-set method |
| BRAKER1 | Hoff 2016 *Bioinformatics* | RNA-seq only | spliced-read intron hints train GeneMark-ET |
| BRAKER2 | Brůna 2021 *NAR Genom Bioinform* | protein only (broad OrthoDB) | ProtHint mines hints from a remote protein DB |
| GALBA | Brůna 2023 *BMC Bioinformatics* | protein only (close relatives) | beats BRAKER2 on large vertebrate genomes with good close proteomes |
| GeMoMa | Keilwagen 2018 *BMC Bioinformatics* | reference annotation + intron-position conservation | project an existing close-relative annotation |
| Funannotate | Palmer & Stajich 2020 (Zenodo) | any | **fungal de facto standard**; train->predict(EVM)->update(PASA) |
| MAKER2 / EVM | Holt 2011; Haas 2008 | many tracks | combiner / build-it-yourself route; transparent evidence weighting |
| Helixer / Tiberius | Stiehler 2020; Gabriel 2024 | none (ab initio, DL) | evidence-poor genomes in well-represented clades |
| AUGUSTUS / GeneMark-ES | Stanke 2006; Lomsadze | hints / self-train | components; standalone ab initio is the last resort |

OrthoDB rule: BRAKER2/3 want a **clade partition** (pick the smallest partition that still contains the target clade - Vertebrata for a fish, not all Metazoa). GALBA wants a few **close-relative proteomes**, not a broad clade.

## Decision Tree by Scenario

| Evidence / scenario | Recommended | Why |
|---------------------|-------------|-----|
| RNA-seq + protein DB | BRAKER3 | state-of-the-art at all genome sizes |
| RNA-seq only | BRAKER1 | intron hints from spliced reads |
| Protein only, close relatives | GALBA | miniprot-aligned close proteomes train AUGUSTUS |
| Protein only, broad/distant | BRAKER2 | ProtHint mines a remote OrthoDB clade |
| No evidence, represented clade | Tiberius or Helixer | DL ab initio now matches evidence-based on vertebrates |
| Reference annotation of a close relative | GeMoMa | homology + intron-position projection |
| Fungus (any evidence) | Funannotate | tiny-intron-aware; bundled EVM + PASA update |
| Need isoforms + UTRs | add PASA / Iso-Seq update step | predictors emit one CDS-only model per locus |
| Genome not yet masked | -> repeat-annotation (soft-mask first) | mandatory prerequisite |
| Want to assess the result | -> annotation-qc | BUSCO genome-vs-proteome, OMArk, sanity metrics |

## Soft-Masking Is Mandatory (Prerequisite)

Run repeat-annotation to **soft-mask** (repeats -> lowercase) before prediction. Unmasked TEs contain ORFs and pseudo-splice-sites; the predictor calls thousands of spurious genes inside repeats (catastrophic in plants where >80% of the genome can be TE) and TE domains pollute training. Pass `--softmasking` so BRAKER honors lowercase as a soft penalty (a real gene can still span a repeat). **Hard-masking (repeats -> N) destroys sequence and truncates real repeat-overlapping genes - avoid it for prediction.** But over-aggressive masking with an uncurated library deletes real multi-copy families (NLR/R-genes, zinc-fingers): filter the repeat library against a protein DB and confirm conserved families survive.

## BRAKER3 (RNA-seq + Protein)

```bash
# Align RNA-seq with a splice-aware aligner; output sorted BAM
hisat2-build masked.fasta idx
hisat2 -x idx -1 R1.fq.gz -2 R2.fq.gz --dta -p 16 | samtools sort -@4 -o rnaseq.bam
samtools index rnaseq.bam

# BRAKER3: protein = an OrthoDB clade partition (smallest that contains the clade)
braker.pl --genome=masked.fasta --prot_seq=Vertebrata.fa \
    --bam=rnaseq.bam --softmasking --threads=16 --species=my_species \
    --gff3 --workingdir=braker3_out
```

`--rnaseq_sets_ids=SRR...,SRR... --rnaseq_sets_dirs=/fastq/` auto-downloads/aligns reads in place of `--bam`. Outputs: `braker.gtf`/`braker.gff3` (TSEBRA-combined), `braker.codingseq`, `braker.aa`.

## GALBA (Protein-Only, Close Relatives)

```bash
galba.pl --genome=masked.fasta --prot_seq=close_relatives.faa \
    --species=my_species --threads=16
```

Prefer BRAKER3 whenever RNA-seq exists - intron evidence substantially improves splice-site accuracy.

## Funannotate (Fungi)

```bash
funannotate mask -i assembly.fa -o masked.fa --cpus 16
funannotate train -i masked.fa -o out -l R1.fq -r R2.fq --species "Genus species"
funannotate predict -i masked.fa -o out -s "Genus species" \
    --transcript_evidence transcripts.fa --protein_evidence proteins.fa
funannotate update -i out --cpus 16     # PASA adds UTRs and isoforms
```

## Gene-Model Sanity Statistics with Python

**Goal:** Compute the triage panel that reveals annotation health where gene count and BUSCO cannot - the isoform ratio, mono-exonic fraction, and protein-length distribution.

**Approach:** Load the GFF3 into gffutils; compute the mRNA:gene ratio (1.00 = isoform-naive), the single-exon fraction, and CDS-length stats; flag clade-anomalous values.

```python
import gffutils

MONOEXONIC_FLAG = 0.30   # >30% single-exon in a vertebrate suggests unmasked TEs/pseudogenes/fragments (calibrate per clade)

def gene_model_stats(gff_file):
    db = gffutils.create_db(gff_file, ':memory:', merge_strategy='merge')
    genes = list(db.features_of_type('gene'))
    mrnas = list(db.features_of_type(['mRNA', 'transcript']))
    exon_counts = [len(list(db.children(tx, featuretype='exon'))) for tx in mrnas]
    mono_frac = sum(1 for e in exon_counts if e == 1) / len(exon_counts) if exon_counts else 0
    mrna_per_gene = len(mrnas) / len(genes) if genes else 0
    if mrna_per_gene <= 1.001:
        print('WARNING: one isoform per locus (mRNA:gene == 1.00) -- isoform/UTR-naive; AS analyses untrustworthy')
    if mono_frac > MONOEXONIC_FLAG:
        print(f'WARNING: mono-exonic fraction {mono_frac:.1%} high -- check masking/contamination')
    return {'genes': len(genes), 'mrna_per_gene': mrna_per_gene, 'mono_exonic_fraction': mono_frac}
```

## Hard Biology the Pipeline Gets Wrong

- **One isoform per locus, no UTRs.** Almost every de novo annotation ships a single CDS-only model per gene (mRNA:gene == 1.00). This silently breaks downstream alternative-splicing/isoform-switching analysis (a switch the reference doesn't contain cannot be detected), and missing 3' UTRs break 3'-tag scRNA-seq (10x reads land "intergenic" and are discarded), APA, and miRNA-target work. The only fix is a transcript-evidence update (PASA, or Iso-Seq via `funannotate update`). Human GENCODE has ~4-5 isoforms/gene; a fresh annotation has one.
- **Merge/split errors are invisible to automated QC.** Tandem arrays (NLR clusters, immune loci) fuse into one elongated model; genes split across contig breaks become two partials; read-through transcription fuses two genes (evidence-supported, so especially nasty); a long intron read as intergenic splits one gene in two. Long-read Iso-Seq + a contiguous assembly prevent these; they hide in the length/exon-count tails otherwise.
- **Reference bias against orphan genes.** Protein-evidence pulls models toward known genes and away from lineage-specific/fast-evolving/orphan genes - exactly the novel biology. Apparent "lineage-specific" genes are often just homology-detection failure (Weisman 2020 *PLoS Biol* 18:e3000862). Keep well-supported ab initio/DL calls in repeat-free RNA-seq-supported regions rather than filtering to "evidence-supported only," which amputates the orphan set.
- **Protists break the spliceosome.** Alternative genetic codes (ciliate UAA/UAG -> Gln), trans-splicing (kinetoplastids, nematodes), and polycistronic transcription mean generic eukaryote models truncate or mis-call. Set the correct translation table and know the RNA-processing biology before trusting any predictor.

## Per-Method Failure Modes

### Unmasked or hard-masked genome
**Trigger:** running BRAKER without soft-masking, or hard-masking. **Mechanism:** TE ORFs become genes / masked sequence truncates real genes. **Symptom:** 2x inflated gene count, high mono-exonic fraction, or fragmented models. **Fix:** soft-mask with a curated library; pass `--softmasking`.

### Training on a bad assembly
**Trigger:** annotating a contaminated/fragmented assembly. **Mechanism:** self-trainer learns contaminant/truncated gene structure and applies it genome-wide. **Symptom:** confidently wrong, BUSCO-green models. **Fix:** decontaminate (FCS-GX/BlobTools) and check assembly BUSCO/N50 first.

### Wrong AUGUSTUS species / OrthoDB partition
**Trigger:** a "close enough" pre-trained species or wrong clade partition. **Mechanism:** splice-site/intron-length params or protein hints mismatched. **Symptom:** systematically mis-placed exon boundaries; clean-looking GFF3. **Fix:** train on the target (BRAKER does this); pick the smallest correct OrthoDB clade.

### Expecting isoforms/UTRs from a one-model pipeline
**Trigger:** AS/3'-tag/APA analysis against a de novo annotation. **Mechanism:** one CDS-only model per locus. **Symptom:** discarded scRNA-seq reads; empty AS results. **Fix:** add a PASA/Iso-Seq update step; check mRNA:gene ratio.

### High BUSCO-Duplicated read as success
**Trigger:** treating high D as good. **Mechanism:** uncollapsed haplotigs vs real WGD vs split models. **Symptom:** inflated gene count. **Fix:** if no known WGD and D>5-8%, purge_dups the assembly first; if known polyploid, confirm via synteny/Ks and keep.

## Quantitative Thresholds

| Threshold | Source | Rationale |
|-----------|--------|-----------|
| Soft-mask before prediction | universal | unmasked TEs inflate spurious genes |
| Gene count vs nearest relative (±, reconcile with ploidy) | clade norm | 1.5-2x with no WGD = haplotigs/over-prediction; ~0.5x = over-masking/under-training |
| Mono-exonic fraction ~10-20% (vertebrate) | clade norm | >25-30% = unmasked TEs/pseudogenes/fragments; fungi legitimately higher |
| Protein length unimodal ~300-450 aa | eukaryote norm | sub-100-aa spike = spurious/fragmented; fat left tail = partials |
| BUSCO-Duplicated ~1-3% (clean haploid) | assembly norm | >5-8% with no WGD -> purge_dups before annotating |
| mRNA:gene ratio | annotation structure | == 1.00 means isoform/UTR-naive |
| Pick smallest OrthoDB partition containing the clade | BRAKER guidance | broader = noisier hints, slower |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| Thousands of extra short genes | unmasked repeats | soft-mask; `--softmasking` |
| BRAKER fails mid-run | expired GeneMark key / special chars in FASTA headers | use the container; `sed 's/ .*//' genome.fa` |
| Many single-exon genes | unmasked TEs / contamination / fragmented assembly | verify masking; decontaminate; check N50 |
| Low protein-BUSCO, high genome-BUSCO | predictor missed present genes (training/evidence) | fix evidence/masking, not the assembly |
| AS analysis returns nothing | one-isoform annotation | run PASA/Iso-Seq update |
| Suspiciously few NLR/ZNF genes | over-masked with uncurated library | filter repeat library against a protein DB |

## References

- Stanke M, et al. 2006. Gene prediction with a hidden Markov model and a new intron submodel (AUGUSTUS). *BMC Bioinformatics* 7:62.
- Hoff KJ, et al. 2016. BRAKER1: unsupervised RNA-Seq-based genome annotation with GeneMark-ET and AUGUSTUS. *Bioinformatics* 32:767-769.
- Brůna T, et al. 2021. BRAKER2: automatic eukaryotic genome annotation with GeneMark-EP+ and AUGUSTUS supported by a protein database. *NAR Genom Bioinform* 3:lqaa108.
- Gabriel L, et al. 2024. BRAKER3: fully automated genome annotation using RNA-seq and protein evidence with GeneMark-ETP, AUGUSTUS, and TSEBRA. *Genome Res* 34:769-777.
- Brůna T, et al. 2024. GeneMark-ETP significantly improves the accuracy of automatic annotation of large eukaryotic genomes. *Genome Res* 34:757-768.
- Gabriel L, et al. 2021. TSEBRA: transcript selector for BRAKER. *BMC Bioinformatics* 22:566.
- Brůna T, et al. 2023. GALBA: genome annotation with miniprot and AUGUSTUS. *BMC Bioinformatics* 24:327.
- Keilwagen J, et al. 2018. Combining RNA-seq data and homology-based gene prediction for plants, animals and fungi (GeMoMa). *BMC Bioinformatics* 19:189.
- Haas BJ, et al. 2008. Automated eukaryotic gene structure annotation using EVidenceModeler. *Genome Biol* 9:R7.
- Haas BJ, et al. 2003. Improving the Arabidopsis genome annotation using maximal transcript alignment assemblies (PASA). *Nucleic Acids Res* 31:5654-5666.
- Gabriel L, et al. 2024. Tiberius: end-to-end deep learning with an HMM for gene prediction. *Bioinformatics* 40:btae685.
- Stiehler F, et al. 2020. Helixer: cross-species gene annotation of large eukaryotic genomes using deep learning. *Bioinformatics* 36:5291-5298.
- Manni M, et al. 2021. BUSCO update. *Mol Biol Evol* 38:4647-4654.
- Weisman CM, et al. 2020. Many, but not all, lineage-specific genes can be explained by homology detection failure. *PLoS Biol* 18:e3000862.
- Palmer JM, Stajich J. 2020. Funannotate v1.8: eukaryotic genome annotation. Zenodo. doi:10.5281/zenodo.4054262.

## Related Skills

- repeat-annotation - PREREQUISITE: soft-mask repeats before prediction
- functional-annotation - Add GO/KEGG/Pfam to predicted proteins
- annotation-qc - BUSCO genome-vs-proteome, OMArk, gene-set sanity metrics
- ncrna-annotation - ncRNAs are not found by protein-coding prediction
- read-alignment/star-alignment - Splice-aware RNA-seq alignment for evidence
- genome-assembly/assembly-qc - Verify assembly quality and purge haplotigs before prediction

## Usage Guide

# Eukaryotic Gene Prediction - Usage Guide

## Overview

Predict protein-coding gene structures in eukaryotic genomes by matching the pipeline to the available evidence: BRAKER3 (RNA-seq + protein), BRAKER1 (RNA-seq), GALBA or BRAKER2 (protein-only), Funannotate (fungi), GeMoMa (homology projection from a close relative), or Helixer/Tiberius (deep-learning ab initio when no evidence exists). The decisions that matter most are upstream of the tool: soft-mask repeats first, decontaminate and check assembly contiguity before training, and pick the right OrthoDB clade partition. Output is gene models in GFF3/GTF with protein and CDS sequences.

## Prerequisites

```bash
# BRAKER3 (wraps AUGUSTUS + GeneMark-ETP + TSEBRA) - prefer the official container for reproducibility
conda install -c bioconda braker3

# Protein-only and homology routes
conda install -c bioconda galba

# Fungal end-to-end pipeline
conda install -c bioconda funannotate

# Evidence prep + evaluation
conda install -c bioconda hisat2 star samtools busco

# Python parsing
pip install gffutils pandas
```

Requires a **soft-masked** genome assembly (run repeat-annotation first). Pin the OrthoDB partition version and the repeat library for reproducibility.

## Quick Start

Tell your AI agent what you want to do:
- "Predict genes in my eukaryotic genome using RNA-seq and protein evidence"
- "Run BRAKER3 on my soft-masked plant genome and check the gene-model sanity metrics"
- "I only have protein evidence from a close relative - which pipeline should I use?"
- "Annotate my fungal genome with Funannotate including UTRs and isoforms"

## Example Prompts

### Evidence-Matched Prediction

> "Run BRAKER3 on my soft-masked genome with these RNA-seq BAM files and the Vertebrata OrthoDB partition, and report mono-exonic fraction and protein-length distribution."

> "I have no RNA-seq and only distant proteins - run BRAKER2 with a broad OrthoDB clade, or Tiberius ab initio since this is a vertebrate."

### Protein-Only and Fungi

> "I have proteomes from two close relatives - run GALBA on my assembly."

> "Annotate my fungal genome with Funannotate, then run the update step to add UTRs and isoforms."

### Diagnosing a Poor Annotation

> "My annotation has 45,000 genes for a vertebrate - check whether this is haplotigs, unmasked repeats, or split models."

> "Compare assembly-BUSCO to proteome-BUSCO to tell whether my predictor missed present genes or the assembly is incomplete."

## What the Agent Will Do

1. Confirm the assembly is soft-masked (repeats in lowercase) and decontaminated, and check contiguity before training
2. Choose the pipeline from available evidence (BRAKER3 > BRAKER1/2 > GALBA/Funannotate/GeMoMa > DL ab initio)
3. Prepare evidence (splice-aware RNA-seq alignment; smallest OrthoDB partition containing the clade)
4. Run the predictor from its container with the correct species/clade parameters
5. Extract protein and CDS sequences
6. Run the triage panel: gene count vs relative, mono-exonic fraction, protein-length distribution, mRNA:gene ratio, BUSCO genome-vs-proteome
7. Flag failure signatures and recommend a PASA/Iso-Seq update step if isoforms/UTRs are needed

## Tips

- **Soft-masking is essential** - Hard-masking truncates real repeat-overlapping genes; soft-masking lets a real gene span a repeat. Filter the repeat library against a protein DB so NLR/zinc-finger families survive.
- **Training quality dominates** - A finder trained on a contaminated/fragmented assembly is confidently wrong genome-wide and BUSCO-green. Decontaminate and check assembly BUSCO/N50 first.
- **OrthoDB clade** - Pick the smallest partition that still contains the clade (Vertebrata for a fish, not all Metazoa). GALBA wants a few close-relative proteomes instead.
- **One isoform, no UTRs by default** - If `mRNA:gene == 1.00`, the annotation is isoform/UTR-naive; alternative-splicing and 3'-tag scRNA-seq analyses against it are untrustworthy. Add a PASA/Iso-Seq update step.
- **Fungi -> Funannotate** - It is the de facto fungal standard (tiny-intron-aware, bundled EVM + PASA update); BRAKER's `--fungus` flag exists but Funannotate is the smoother fungal path.
- **High BUSCO-Duplicated** - >5-8% with no known WGD means purge_dups the assembly first, not "deduplicate genes" afterward. In a known polyploid, high D is real - confirm via synteny/Ks and keep.
- **Reproducibility** - Run from official containers; the GFF3 alone is not reproducible without the masked genome, evidence, trained parameters, and versions.

## Related Skills

- genome-annotation/repeat-annotation - Soft-mask repeats before gene prediction
- genome-annotation/functional-annotation - Add functional annotation to predicted genes
- genome-annotation/annotation-qc - BUSCO genome-vs-proteome, OMArk, gene-set sanity
- read-alignment/star-alignment - Splice-aware RNA-seq aligner for evidence
- genome-assembly/assembly-qc - Verify assembly quality and purge haplotigs first

## Bundled Files

- `genome-annotation--eukaryotic-gene-prediction--examples--braker3_pipeline.sh` — copied from `examples/braker3_pipeline.sh`
- `genome-annotation--eukaryotic-gene-prediction--examples--galba_protein_only.sh` — copied from `examples/galba_protein_only.sh`
