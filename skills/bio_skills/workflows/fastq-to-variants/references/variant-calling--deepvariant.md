# bio-variant-calling-deepvariant

> Bundled component reference for `variant-calling/deepvariant` (original source: `skills/bio_skills/variant-calling/deepvariant`).

Calls germline SNPs and indels with Google DeepVariant, which reframes variant calling as CNN image classification over multi-channel pileup tensors. Covers platform-specific model selection (WGS, WES, PACBIO, ONT_R104, HYBRID_PACBIO_ILLUMINA), one-shot run_deepvariant vs the three-stage make_examples/call_variants/postprocess_variants pipeline, GPU acceleration of call_variants, DeepTrio for family/trio and de-novo calling, and joint genotyping of gVCFs with GLnexus (not GenotypeGVCFs). Use when deciding DeepVariant vs GATK vs DRAGEN, picking the right --model_type for a sequencing platform, avoiding post-hoc GATK hard filters or BQSR that degrade CNN calls, calling de-novo variants in a trio, merging a DeepVariant cohort, or weighing GIAB-trained benchmark accuracy before clinical deployment.

## Instructions

## Version Compatibility

Reference examples tested with: DeepVariant 1.6.1+, GLnexus 1.4+, bcftools 1.19+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `docker run google/deepvariant:<tag> /opt/deepvariant/bin/run_deepvariant --helpfull | head` to confirm flags and available `--model_type` tokens for the build
- `bcftools --version` and `bcftools --help` to confirm flags

If code throws errors, introspect the installed container and adapt the example
to match the actual API rather than retrying.

Note: newer DeepVariant releases (1.8.x+) add model types and rename image tags; always confirm the `--model_type` tokens against the exact container in use rather than assuming this list is complete.

# DeepVariant Variant Calling

**"Call germline variants with DeepVariant"** -> Render each candidate site's read pileup as a multi-channel image and classify its genotype with a trained CNN.
- CLI: `run_deepvariant` (one-shot) or `make_examples` -> `call_variants` -> `postprocess_variants` (three-stage), shipped as a Docker/Singularity container

## The governing principle

DeepVariant replaces the parametric HMM/Bayesian genotyper with a trained convolutional neural network that classifies pileup images into hom-ref / het / hom-alt. Two consequences drive every downstream decision:

1. **There is NO hand-tuned statistical filter to apply afterward.** The CNN already emits a calibrated FILTER column (`PASS` for confident variants, `RefCall` for sites judged homozygous reference). Applying GATK hard filters (QD/FS/MQ/SOR thresholds) or VQSR on top of DeepVariant output removes true positives, not false ones -- those annotations do not even exist in the VCF. Post-call handling is limited to QUAL/GQ thresholding, normalization, and region restriction.
2. **The network learned its error model from RAW base qualities**, so running BQSR upstream costs runtime and slightly LOWERS DeepVariant accuracy. DeepVariant's own guidance is to skip BQSR. The input requirement is a sorted, indexed, duplicate-marked BAM/CRAM -- nothing more.

DeepVariant calls germline variants only. For somatic calling use DeepSomatic (a separate tool from the same team); the diploid genotype classes cannot represent subclonal allele fractions.

## How DeepVariant Works

Three stages, run together by `run_deepvariant` or separately for control over intermediates:

1. **`make_examples`** (CPU-bound, the runtime bottleneck) scans the BAM for candidate sites where non-reference support passes a permissive recall-tuned screen, then renders each candidate as a multi-channel pileup image written to sharded TFRecords. Rows are reads, columns are reference positions; channels encode read base identity, base quality, mapping quality, strand, whether the read supports the candidate allele, and whether the base differs from the reference. Illumina models add an insert-size channel; long-read models add a haplotype channel. Exact tensor dimensions are version-dependent -- treat any published figure as illustrative. Parallelized by `--num_shards`.
2. **`call_variants`** runs the trained Inception-family CNN over each example and emits a 3-class genotype-likelihood output. This is the only GPU-accelerable stage.
3. **`postprocess_variants`** sorts CNN outputs, resolves multiallelics, and converts likelihoods to VCF/gVCF.

This image-based design is why DeepVariant beats parametric callers on indels and in difficult contexts (homopolymers, tandem repeats, low-complexity regions): the CNN learns visual patterns in pileup geometry that heuristic filters miss. Models are platform-specific because sequencer error modes (Illumina substitutions, ONT homopolymer indels) are visually different and each model learns the artifact distribution of its training platform.

## Model Selection

`--model_type` is load-bearing: using the wrong model silently degrades accuracy because the CNN expects platform-specific error patterns in the pileup and does NOT error out. Match the model to the instrument that produced the reads, not to the analysis goal.

| `--model_type` | Use for | Trained on | Fails / degrades when |
|----------------|---------|-----------|-----------------------|
| `WGS` | Illumina short-read WGS | 30-50x PCR-free Illumina | applied to exome without `--regions`, to long reads, or to PCR-amplicon data |
| `WES` | Illumina exome/targeted | capture exome | run without a `--regions` BED (wastes hours scanning off-target genome) |
| `PACBIO` | PacBio HiFi (CCS) | HiFi, Q30+ per-read | applied to CLR reads (Q10-15 error profile the model never saw) |
| `ONT_R104` | ONT R10.4+ chemistry | R10.4 simplex/duplex | applied to R9.4 data (use Clair3's R9.4 model); accuracy still below HiFi |
| `HYBRID_PACBIO_ILLUMINA` | samples with BOTH HiFi and Illumina | mixed HiFi+Illumina | only one platform is available |

## When to Use DeepVariant vs GATK vs DRAGEN

- **DeepVariant** -- best indel accuracy and best difficult-region/long-read performance among open tools; generalizes across platforms with a model swap; needs no filter tuning. Default choice for indels, difficult regions, and long reads.
- **GATK HaplotypeCaller** -- every parameter auditable, mature joint calling with reference-confidence squaring-off, and regulatory precedent. Prefer for very large cohorts needing GenomicsDB scaling or clinical pipelines already validated on GATK. See variant-calling/gatk-variant-calling.
- **DRAGEN** -- FPGA-accelerated, ~20-25 min per 30x genome, wins the difficult-to-map benchmarks; prefer for throughput when the hardware or cloud is available (subject to the GIAB-overfitting caveat below).

The full engine-selection decision table lives in variant-calling/variant-calling -- consult it before committing a production pipeline; the choice depends on cohort size, platform, auditability, and throughput, not on accuracy alone.

## Installation

```bash
docker pull google/deepvariant:1.6.1

# GPU support (NVIDIA GPU + nvidia-container-toolkit required)
docker pull google/deepvariant:1.6.1-gpu

# Singularity alternative
singularity pull docker://google/deepvariant:1.6.1
```

## One-Shot Run

```bash
docker run -v "${PWD}:/input" -v "${PWD}/output:/output" \
    google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WGS \
    --ref=/input/reference.fa \
    --reads=/input/sample.bam \
    --output_vcf=/output/sample.vcf.gz \
    --output_gvcf=/output/sample.g.vcf.gz \
    --num_shards=16
```

Always generate a gVCF (`--output_gvcf`) even for a single sample -- it enables downstream joint calling with GLnexus without re-running DeepVariant.

Exome/targeted calling adds `--regions`:

```bash
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WES \
    --ref=/data/reference.fa \
    --reads=/data/exome.bam \
    --regions=/data/targets.bed \
    --output_vcf=/data/exome.vcf.gz \
    --num_shards=8
```

PacBio HiFi and ONT differ only in `--model_type=PACBIO` or `--model_type=ONT_R104`. HiFi's Q30+ reads give the CNN clean pileups; R10.4+ chemistry substantially reduces the systematic homopolymer-indel errors that made earlier ONT chemistries unusable for short-variant calling.

## Three-Stage Pipeline

For control over intermediates (custom sharding, resuming, mixing CPU/GPU nodes), run the stages separately:

```bash
# Stage 1: render pileup images (CPU-bound; parallelize with sharded --examples)
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/make_examples \
    --mode calling \
    --ref /data/reference.fa \
    --reads /data/sample.bam \
    --examples /data/examples.tfrecord.gz \
    --gvcf /data/gvcf.tfrecord.gz

# Stage 2: CNN inference (the GPU-accelerable stage)
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/call_variants \
    --outfile /data/call_variants.tfrecord.gz \
    --examples /data/examples.tfrecord.gz \
    --checkpoint /opt/models/wgs

# Stage 3: emit VCF/gVCF
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/postprocess_variants \
    --ref /data/reference.fa \
    --infile /data/call_variants.tfrecord.gz \
    --outfile /data/output.vcf.gz \
    --gvcf_outfile /data/output.g.vcf.gz \
    --nonvariant_site_tfrecord_path /data/gvcf.tfrecord.gz
```

## GPU Acceleration

GPU acceleration benefits ONLY `call_variants` (CNN inference); `make_examples` and `postprocess_variants` are CPU-bound and scale with `--num_shards`. For large cohorts, parallelizing across samples on CPU nodes is often more cost-effective than queuing for GPUs.

```bash
docker run --gpus all -v "${PWD}:/data" \
    google/deepvariant:1.6.1-gpu \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WGS \
    --ref=/data/reference.fa \
    --reads=/data/sample.bam \
    --output_vcf=/data/output.vcf.gz \
    --num_shards=16
```

## DeepTrio (Family / Trio Calling)

DeepTrio extends the pileup image to span proband plus both parents simultaneously, so the CNN learns inheritance context and calls de-novo variants directly. This beats naive trio subtraction, whose apparent de-novo set is dominated by false positives from independent per-sample errors. Use DeepTrio for family studies, Mendelian-consistency work, and de-novo discovery. It ships proband and parent models for Illumina WGS/WES and PacBio (`--model_type WGS|WES|PACBIO`) and uses a separate image tag (`deeptrio-<version>`).

```bash
docker run -v "${PWD}:/data" google/deepvariant:deeptrio-1.6.1 \
    /opt/deepvariant/bin/run_deeptrio \
    --model_type=WGS \
    --ref=/data/reference.fa \
    --reads_child=/data/child.bam \
    --reads_parent1=/data/father.bam \
    --reads_parent2=/data/mother.bam \
    --sample_name_child=CHILD \
    --sample_name_parent1=FATHER \
    --sample_name_parent2=MOTHER \
    --output_vcf_child=/data/child.vcf.gz \
    --output_vcf_parent1=/data/father.vcf.gz \
    --output_vcf_parent2=/data/mother.vcf.gz \
    --output_gvcf_child=/data/child.g.vcf.gz \
    --output_gvcf_parent1=/data/father.g.vcf.gz \
    --output_gvcf_parent2=/data/mother.g.vcf.gz \
    --num_shards=16
```

Merge the three per-sample gVCFs with GLnexus (below) into one trio VCF; the joint context is what supports Mendelian-violation and de-novo-rate analysis.

## Joint Calling with GLnexus

DeepVariant gVCFs are joint-genotyped with GLnexus, NOT GATK GenotypeGVCFs -- GLnexus performs allele unification across per-sample gVCFs and grows its database incrementally as samples are added, avoiding full-cohort reprocessing. See variant-calling/joint-calling for the GATK reference-confidence alternative and when each is appropriate.

```bash
for bam in *.bam; do
    sample=$(basename "$bam" .bam)
    docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
        /opt/deepvariant/bin/run_deepvariant \
        --model_type=WGS --ref=/data/reference.fa --reads=/data/$bam \
        --output_vcf=/data/${sample}.vcf.gz \
        --output_gvcf=/data/${sample}.g.vcf.gz \
        --num_shards=16
done

docker run -v "${PWD}:/data" quay.io/mlin/glnexus:v1.4.1 \
    /usr/local/bin/glnexus_cli \
    --config DeepVariantWGS \
    /data/*.g.vcf.gz \
    | bcftools view - -Oz -o cohort.vcf.gz
```

| GLnexus `--config` | Use case | Notes |
|--------------------|----------|-------|
| `DeepVariantWGS` | Illumina WGS gVCFs | Default for most WGS cohorts |
| `DeepVariantWES` | Illumina exome gVCFs | Tuned for higher-depth, narrower-region calling |
| `DeepVariant_unfiltered` | Keep all variant sites | Research exploration; more false positives, useful for trio/de-novo where RefCall sites matter |

The DeepVariant+GLnexus path is a strong open-source alternative to GATK joint calling. Representative benchmark (Yun et al. 2020, GIAB, 40x WGS): cohort Mendelian-violation rate 1.7% vs GATK-VQSR 5.0%; SNP F1 error 0.07% vs 1.23%; indel F1 error 1.14% vs 2.92%. On a 2,504-sample cohort the GLnexus merge ran ~8x faster on chromosome 22 (0.84 h vs 6.83 h) and DeepVariant gVCFs were ~7x smaller on disk genome-wide (2.20 TB vs 15.16 TB). These figures are sample-, coverage-, and version-specific -- not fixed constants.

## Output and Quality Control

DeepVariant output is already CNN-filtered (`PASS` / `RefCall` in FILTER). Do NOT apply GATK hard filters or VQSR. Legitimate post-call handling is QUAL/GQ thresholding, normalization, and region restriction.

```bash
bcftools stats output.vcf.gz > stats.txt

# Ti/Tv sanity check: expect ~2.0-2.1 for WGS, ~3.0-3.3 for WES
bcftools stats output.vcf.gz | grep TSTV

# QUAL is CNN confidence; GQ is genotype quality. Threshold, do not re-filter on GATK annotations.
bcftools view -i 'QUAL>20 && FMT/GQ>20' output.vcf.gz -Oz -o filtered.vcf.gz
```

## Benchmarking and the GIAB Circularity Caveat

Benchmark against a GIAB truth set with a haplotype-aware comparator (hap.py + vcfeval), restricted to the confident-region BED and stratified by region difficulty:

```bash
docker run -v "${PWD}:/data" jmcdani20/hap.py:latest \
    /opt/hap.py/bin/hap.py \
    /data/HG002_GRCh38_truth.vcf.gz \
    /data/deepvariant_output.vcf.gz \
    -f /data/HG002_confident.bed \
    -r /data/reference.fa \
    -o /data/benchmark \
    --engine=vcfeval --threads 16
```

The load-bearing caveat: DeepVariant is TRAINED on GIAB truth sets (primarily HG001) and then routinely BENCHMARKED on GIAB samples. When train and test both derive from HG001-HG007, a headline F1 of 0.999 partly measures memorization of the truth set's idiosyncrasies, not generalization. The honest read weights held-out-sample performance (train on HG001/3/4/5/6/7, test on HG002 -- as precisionFDA V2 did by scoring the semi-blinded parents HG003/HG004), reports difficult-region and CMRG strata rather than one genome-wide number, and -- before clinical deployment -- validates on population-matched, characterized material rather than trusting a published GIAB F1. A benchmark that reports one global F1 without stratification and without a held-out or non-GIAB sample is not decision-grade (Krusche et al. 2019).

## Approximate Accuracy vs Other Callers

Approximate F1 from GIAB HG002/HG003/HG004 on GRCh38; exact values vary by sample, coverage, and version. On easy SNPs every modern caller exceeds F1 0.999, so the decision-relevant gaps are indels and difficult regions.

| Caller | SNP F1 | Indel F1 | Speed (30x WGS) | Notes |
|--------|--------|----------|-----------------|-------|
| DeepVariant | ~0.999 | ~0.993 | ~4-6 h CPU, ~1-2 h GPU | Highest open-tool indel accuracy; slow without GPU |
| GATK HaplotypeCaller | ~0.999 | ~0.989 | ~4-8 h CPU | Auditable; joint-calling ecosystem |
| Strelka2 | ~0.998 | ~0.960 | ~1-2 h CPU | Fast; no longer actively maintained |
| Clair3 | ~0.998 | ~0.980 | ~8 h (50x ONT) | Strong for long reads; active development |

## Resource Requirements

| Data | RAM | CPU time | GPU time | Notes |
|------|-----|----------|----------|-------|
| WGS 30x | 64 GB | ~4-6 h | ~1-2 h | `--num_shards` scales make_examples linearly |
| WES | 32 GB | ~30 min | ~10 min | Smaller target region |
| PacBio HiFi 30x | 64 GB | ~3-5 h | ~1-2 h | Fewer but longer reads |
| ONT 50x | 64 GB | ~6-8 h | ~2-3 h | Higher error rate -> more candidate sites |

## Common Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| Accuracy far below published F1 | Wrong `--model_type` for the platform (silent degradation, no error) | Match the model to the instrument (WGS/WES/PACBIO/ONT_R104) |
| Applying GATK hard filters removes true variants | DeepVariant has no QD/FS/MQ annotations; the CNN already filtered | Threshold on QUAL/GQ only; never run VQSR or hard filters on DeepVariant output |
| Slightly worse calls than expected on Illumina | BQSR was run upstream | Skip BQSR; DeepVariant learned its error model from raw qualities |
| WES run takes hours scanning empty genome | `--regions` BED omitted | Always pass `--regions` for exome/targeted data |
| GPU gives little speedup | Only `call_variants` uses the GPU; make_examples is CPU-bound | Raise `--num_shards` for the CPU stages; use GPU for call_variants |
| Trio de-novo set is full of false positives | Naive per-sample subtraction | Use DeepTrio, which learns inheritance context directly |
| Joint calling fails with GenotypeGVCFs | DeepVariant gVCFs are not GATK reference-confidence gVCFs | Merge with GLnexus, not GenotypeGVCFs |
| No `Number=R` / allele-specific fields for filtering | DeepVariant does not emit them | Do not build a GATK-style filter; rely on the CNN FILTER + QUAL/GQ |

## Related Skills

- variant-calling/gatk-variant-calling - GATK HaplotypeCaller alternative with auditable parameters, joint calling, and VQSR/VETS
- variant-calling/variant-calling - engine-selection decision table (DeepVariant vs GATK vs DRAGEN vs bcftools) and lightweight bcftools calling
- variant-calling/joint-calling - GATK reference-confidence joint genotyping, the alternative to GLnexus for cohorts
- variant-calling/filtering-best-practices - post-calling filtering for callers that DO expose hard-filter annotations (not DeepVariant)
- variant-calling/vcf-statistics - QC metrics (Ti/Tv, het/hom) for the called VCF
- long-read-sequencing/clair3-variants - long-read variant-calling alternative, especially for ONT R9.4 and resource-constrained settings

## References

- Poplin R, Chang P-C, Alexander D, et al. A universal SNP and small-indel variant caller using deep neural networks. *Nature Biotechnology* 36(10):983-987 (2018). DOI 10.1038/nbt.4235. (DeepVariant.)
- Yun T, Li H, Chang P-C, Lin MF, Carroll A, McLean CY. Accurate, scalable cohort variant calls using DeepVariant and GLnexus. *Bioinformatics* 36(24):5582-5589 (2020). DOI 10.1093/bioinformatics/btaa1081. (DeepVariant+GLnexus cohort benchmark.)
- Kolesnikov A, Goel S, Nattestad M, et al. DeepTrio: Variant Calling in Families Using Deep Learning. *bioRxiv* 2021.04.05.438434 (2021). DOI 10.1101/2021.04.05.438434. (Preprint; DeepTrio.)
- Shafin K, Pesout T, Chang P-C, et al. Haplotype-aware variant calling with PEPPER-Margin-DeepVariant enables high accuracy in nanopore long-reads. *Nature Methods* 18:1322-1332 (2021). DOI 10.1038/s41592-021-01299-w. (ONT long-read path.)
- Krusche P, Trigg L, Boutros PC, et al. Best practices for benchmarking germline small-variant calls in human genomes. *Nature Biotechnology* 37:555-560 (2019). DOI 10.1038/s41587-019-0054-x. (hap.py/vcfeval, confident regions, stratification.)
- Olson ND, Wagner J, McDaniel J, et al. PrecisionFDA Truth Challenge V2: Calling variants from short and long reads in difficult-to-map regions. *Cell Genomics* 2(5):100129 (2022). DOI 10.1016/j.xgen.2022.100129. (Held-out scoring; difficult-region performance.)

## Usage Guide

# DeepVariant - Usage Guide

## Overview

Deep learning variant calling using Google's DeepVariant for high-accuracy germline SNP and indel detection from Illumina, PacBio HiFi, or Oxford Nanopore data.

## Prerequisites

```bash
# Docker (recommended)
docker pull google/deepvariant:1.6.1

# GPU version
docker pull google/deepvariant:1.6.1-gpu

# DeepTrio (separate image tag)
docker pull google/deepvariant:deeptrio-1.6.1

# Singularity
singularity pull docker://google/deepvariant:1.6.1
```

Input is a sorted, indexed, duplicate-marked BAM/CRAM. Do NOT run BQSR first -- DeepVariant learned its error model from raw base qualities and BQSR slightly lowers its accuracy.

## Quick Start

Tell your AI agent what you want to do:
- "Call variants from my WGS BAM using DeepVariant"
- "Run DeepVariant on exome data with target regions"
- "Set up DeepVariant with GPU acceleration"
- "Generate GVCFs for joint calling with GLnexus"
- "Call de-novo variants in my trio with DeepTrio"
- "Should I use DeepVariant, GATK, or DRAGEN for this cohort?"

## Example Prompts

### Basic Variant Calling
> "Call variants from my whole genome BAM using DeepVariant"

> "Run DeepVariant on sample.bam with 16 threads"

### Exome/Targeted
> "Run DeepVariant on my exome data with the capture BED file"

> "Call variants only in my target regions using DeepVariant WES model"

### Long Reads
> "Call variants from my PacBio HiFi reads with DeepVariant"

> "Run DeepVariant with the ONT_R104 model for Nanopore data"

### Multi-Sample
> "Generate GVCFs with DeepVariant for joint calling"

> "Set up DeepVariant + GLnexus for my cohort of 20 samples"

### Family / Trio
> "Run DeepTrio on my proband-father-mother BAMs and flag de-novo variants"

> "Joint genotype my DeepTrio gVCFs and check Mendelian consistency"

### GPU Acceleration
> "Run DeepVariant with GPU support for faster processing"

## What the Agent Will Do

1. Verify input BAM is aligned, sorted, indexed, and duplicate-marked (and that BQSR was NOT applied)
2. Select the model type matching the sequencing instrument (WGS, WES, PACBIO, ONT_R104, HYBRID_PACBIO_ILLUMINA)
3. Set up the Docker/Singularity command with volume mounts, one-shot or three-stage
4. Run DeepVariant with an appropriate `--num_shards`; use GPU only for call_variants
5. Generate VCF and, when a cohort is planned, gVCF for GLnexus joint calling
6. For families, run DeepTrio and merge the trio gVCFs with GLnexus
7. Produce variant statistics and, when a truth set is available, a stratified hap.py/vcfeval benchmark

## Tips

- Match the model to the instrument, not the analysis goal -- the wrong `--model_type` silently degrades accuracy without erroring
- Do NOT apply GATK hard filters or VQSR to DeepVariant output; the CNN already filtered it (FILTER = PASS / RefCall). Threshold on QUAL/GQ only
- Do NOT run BQSR upstream; it slightly lowers DeepVariant accuracy
- Always specify `--regions` for exome/targeted data to save time
- GPU accelerates only the call_variants stage; make_examples and postprocess_variants are CPU-bound (scale with `--num_shards`)
- Generate gVCFs with `--output_gvcf` if planning multi-sample joint calling
- Use GLnexus (not GATK GenotypeGVCFs) for joint genotyping DeepVariant gVCFs
- Use DeepTrio for de-novo calling; naive trio subtraction produces mostly false de-novos
- Ti/Tv around 2.0-2.1 (WGS) or 3.0-3.3 (WES) indicates high-quality SNP calls
- DeepVariant is trained on GIAB then benchmarked on GIAB; weight held-out/non-GIAB-ancestry performance and validate on characterized material before clinical use

## Model Types

| Model | Data Type |
|-------|-----------|
| `WGS` | Illumina whole genome |
| `WES` | Illumina exome/targeted |
| `PACBIO` | PacBio HiFi |
| `ONT_R104` | Oxford Nanopore R10.4+ |
| `HYBRID_PACBIO_ILLUMINA` | Samples with both HiFi and Illumina |

## Usage Patterns

### Basic WGS

```bash
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WGS \
    --ref=/data/reference.fa \
    --reads=/data/sample.bam \
    --output_vcf=/data/output.vcf.gz \
    --output_gvcf=/data/output.g.vcf.gz \
    --num_shards=16
```

### Exome/Targeted Sequencing

```bash
docker run -v "${PWD}:/data" google/deepvariant:1.6.1 \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WES \
    --ref=/data/reference.fa \
    --reads=/data/exome.bam \
    --regions=/data/targets.bed \
    --output_vcf=/data/output.vcf.gz \
    --num_shards=8
```

### GPU Acceleration

```bash
docker run --gpus all -v "${PWD}:/data" google/deepvariant:1.6.1-gpu \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WGS \
    --ref=/data/reference.fa \
    --reads=/data/sample.bam \
    --output_vcf=/data/output.vcf.gz
```

### Multi-Sample with GLnexus

1. Generate gVCFs for each sample with `--output_gvcf`
2. Joint genotype with GLnexus:

```bash
docker run -v "${PWD}:/data" quay.io/mlin/glnexus:v1.4.1 \
    /usr/local/bin/glnexus_cli --config DeepVariantWGS \
    /data/*.g.vcf.gz | bcftools view - -Oz -o cohort.vcf.gz
```

## Quality Control

```bash
# Statistics
bcftools stats output.vcf.gz > stats.txt

# Filter low quality
bcftools view -i 'QUAL>20 && FMT/GQ>20' output.vcf.gz -Oz -o filtered.vcf.gz

# Ti/Tv ratio (expect ~2.0-2.1 for WGS)
bcftools stats output.vcf.gz | grep TSTV
```

## Resource Requirements

| Data Type | Memory | Time (30x) |
|-----------|--------|------------|
| WGS | 64 GB | 4-6 hours |
| WES | 32 GB | 30 min |
| WGS + GPU | 32 GB | 1-2 hours |

## Related Skills

- variant-calling/variant-calling - Engine-selection table (DeepVariant vs GATK vs DRAGEN) and lightweight bcftools calling
- variant-calling/gatk-variant-calling - GATK HaplotypeCaller alternative with joint calling and VQSR/VETS
- variant-calling/joint-calling - GATK reference-confidence joint genotyping, the alternative to GLnexus
- variant-calling/vcf-basics - View and query VCF output
- variant-calling/filtering-best-practices - Post-call filtering for callers that expose hard-filter annotations (not DeepVariant)
- variant-calling/vcf-statistics - QC metrics for called variants
- long-read-sequencing/clair3-variants - Long-read alternative, especially for ONT R9.4

## Bundled Files

- `variant-calling--deepvariant--examples--run_deepvariant.sh` — copied from `examples/run_deepvariant.sh`
