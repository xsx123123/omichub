# bio-metagenomics-kraken

> Bundled component reference for `metagenomics/kraken-classification` (original source: `skills/bio_skills/metagenomics/kraken-classification`).

Classifies shotgun metagenomic reads to taxa with Kraken2's minimizer/LCA matching against a chosen reference database, then hands off to Bracken for abundance re-estimation. Covers why the database (not the algorithm) decides what can be detected, the --confidence and --minimum-hit-groups precision levers, unique-minimizer false-positive control, host-read removal, and why raw Kraken2 read counts are not abundances. Use when profiling who-is-there from shotgun reads, choosing a Kraken2 database, setting a confidence threshold, controlling false positives, or feeding reports to Bracken. For marker-gene profiling see metaphlan-profiling; for abundance mechanics see abundance-estimation; for assembly/MAG recovery see genome-assembly/metagenome-assembly.

## Instructions

## Version Compatibility

Reference examples tested with: Kraken2 2.1.3+, Bracken 2.9+, KrakenTools 1.2+, pandas 2.2+.

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `kraken2 --version`, `bracken -h`, `kraken2 --help` to confirm flags and defaults
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

The DATABASE is the version that matters most. A taxon absent from the database is invisible no matter how the binary is configured. Record the Kraken2 database build (Standard / PlusPF / PlusPFP / nt / GTDB, and whether capped to 8/16 GB) and the Bracken `databaseRLENmers.kmer_distrib` read length, which must match both the Kraken2 database and the actual read length. `--minimum-hit-groups` enforcement varied across older 2.x point releases; confirm defaults with `kraken2 --help` on the installed build.

# Kraken Classification

**"What's in my metagenome?"** -> Match each read's k-mers to a reference database by lowest-common-ancestor, then re-estimate abundance with Bracken - because the database, not the algorithm, decides what can be found.
- CLI: `kraken2 --db DB --paired R1.fq.gz R2.fq.gz --report out.kreport --confidence 0.1 --output out.kraken`

Scope: read-based, assembly-free taxonomic classification of shotgun reads, plus the Bracken handoff. Marker-gene profiling -> metaphlan-profiling. Bracken command mechanics -> abundance-estimation. Genome/MAG recovery -> genome-assembly/metagenome-assembly. Host removal and read QC -> read-qc/contamination-screening, contamination-controls. Amplicon/16S -> the microbiome category.

## The Single Most Important Modern Insight -- A Kraken Report Is a Database-Conditioned Similarity Ledger, Not a Sample Inventory

Kraken reports what each read most resembles in THIS database - never what is truly present, and never how much. Every number is hostage to three choices made before the run: the database, the confidence threshold, and the assumption that read count means abundance. Three corollaries each common misuse violates:

1. **Classification is not presence.** At `--confidence 0` with the LCA rule, one shared k-mer labels a read with its nearest database relative even when the true organism is absent. Absence-from-database becomes a confident wrong species.
2. **Read count is not abundance.** Counts scale with genome length and copy number, so the report percentage is a fragment fraction, not a cell fraction. Bracken fixes the wrong-rank problem; it does not fix this.
3. **A taxon at the bottom of the report is a hypothesis, not a finding.** Single-region hits, hash collisions, and contaminated references populate the long tail. Unique-minimizer coverage separates a real low-abundance organism from a phantom.

Organize the analysis around defending against these three, not around listing flags. Kraken2 at defaults over-classifies; Kraken2 tuned (right database + confidence + hit-groups + a unique-k-mer floor + host removal) is competitive with any classifier.

## Why "Exact K-mer" Is Wrong for Kraken2

Kraken1 (Wood & Salzberg 2014 *Genome Biol* 15:R46) stored every exact k-mer. Kraken2 (Wood 2019 *Genome Biol* 20:257) replaced that with three ideas that make it fast and lean but PROBABILISTIC: (a) minimizers collapse each k-mer (default k=35) to the smallest hashed l=31-mer in its window; (b) a spaced seed (s=7 masked positions) tolerates errors at "don't care" positions; (c) a compact hash table stores only high bits of each key. The compact hash can return a wrong or spurious LCA on collision - which is exactly why the precision levers below exist. Calling Kraken2 "exact k-mer" hides where false positives come from.

## Tool Taxonomy

| Tool | Citation | Mechanism / role | When |
|------|----------|------------------|------|
| Kraken2 | Wood 2019 *Genome Biol* 20:257 | minimizer + spaced-seed + compact-hash LCA | fast read classification; database-bound; the default choice |
| Bracken | Lu 2017 *PeerJ Comput Sci* 3:e104 | Bayesian redistribution of reads stranded at higher ranks | always run after Kraken2 for species/genus estimates |
| KrakenUniq | Breitwieser 2018 *Genome Biol* 19:198 | HyperLogLog count of unique k-mers per taxon | false-positive control on hits of interest |
| KMCP | Shen 2023 *Bioinformatics* 39:btac845 | genome-coverage pseudo-mapping | low-depth/clinical/viral where conserved-region FPs hurt |
| sourmash gather | Pierce 2019 *F1000Res* 8:1006 | FracMinHash containment, min-set-cover | "which genomes are present" with calibrated containment |
| MetaPhlAn 4 | Blanco-Miguez 2023 *Nat Biotechnol* 41:1633 | clade-specific marker genes | -> metaphlan-profiling; FP-conservative, abundance directly |

## Decision Tree by Scenario

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Who-is-there, fast, custom database possible | Kraken2 + Bracken | k-mer LCA; Bracken fixes count->rank, not count->cells |
| Need species relative abundance with no database build | -> metaphlan-profiling | marker-based; abundance-conservative; no FP tail |
| Low-biomass / clinical pathogen ID | Kraken2 (high confidence + hit-groups) + KrakenUniq unique-k-mer floor | the FP tail is the enemy; one unique-k-mer filter cuts phantoms |
| Reads not host-depleted / unQC'd | -> contamination-controls, read-qc/contamination-screening first | host reads swamp the profile; references carry human fragments |
| Want abundance comparable across studies | state the database + confidence; do not merge with MetaPhlAn percentages | read fraction != cell fraction; different tools = different quantities |
| Recover genomes / novel taxa / MAGs | -> genome-assembly/metagenome-assembly | classification is assembly-free and database-bound |
| 16S amplicon reads | -> microbiome category | Kraken-on-16S works but amplicon analysis lives there |

## Basic Classification

```bash
# Paired-end, with the precision levers that defaults omit
kraken2 --db "$KRAKEN_DB" \
    --paired --gzip-compressed --threads 8 \
    --confidence 0.1 \            # raise from default 0 to suppress single-k-mer false positives
    --minimum-hit-groups 2 \      # require >=2 distinct hit regions (default 2; raise to 3 for clinical)
    --report out.kreport \
    --output out.kraken \
    R1.fq.gz R2.fq.gz
```

`--paired` joins mates with a k-mer-breaking `N` and classifies the pair as one fragment, raising specificity. The per-read `--output` (large) can be dropped to `/dev/null` once the `.kreport` is what feeds Bracken. `--memory-mapping` runs without loading the database into RAM (slower; for low-memory hosts).

## False-Positive Control: Unique Minimizers

**Goal:** Separate a real low-abundance organism from a single-region phantom before believing any tail taxon.

**Approach:** Enable `--report-minimizer-data` so the report carries distinct-minimizer counts; a taxon with many reads but few distinct minimizers is hitting one conserved region and is a red flag. KrakenUniq's HyperLogLog unique-k-mer count is the heavier-weight version of the same signal.

```bash
kraken2 --db "$KRAKEN_DB" --paired --confidence 0.1 \
    --report-minimizer-data \    # inserts 2 columns: total + DISTINCT minimizers (shifts later columns)
    --report out.kreport --output /dev/null \
    R1.fq.gz R2.fq.gz
# A species with high reads but low distinct-minimizers = false positive (one region lit up repeatedly).
```

Calibrate a unique-k-mer floor against negative controls rather than hard-coding one; the clinical ">=1024 unique k-mers" cutoff is dataset/database-specific folklore, not a constant.

## Build a Custom Database

**Goal:** Build a database whose contents define exactly the detectable universe (and include human for host capture).

**Approach:** Download taxonomy, add the libraries the question needs (including `human`), build the minimizer index, then build the matching Bracken distributions at the actual read length.

```bash
kraken2-build --download-taxonomy --db custom_db
for lib in bacteria archaea viral human UniVec_Core; do
    kraken2-build --download-library "$lib" --db custom_db
done
kraken2-build --build --db custom_db --threads 16    # writes hash.k2d, opts.k2d, taxo.k2d
kraken2-build --clean --db custom_db                 # drop library/ + taxonomy/ to shrink
bracken-build -d custom_db -t 16 -k 35 -l 150        # -k MUST equal the Kraken2 k (35); -l = read length
```

`kraken2-build --special gtdb` builds a GTDB-taxonomy database (curated; the greengenes/silva/rdp special downloads have rotted). `--max-db-size` randomly downsamples k-mers to fit a cap - this is how the prebuilt 8gb/16gb databases are made, and the reason confidence collapses classification on them.

## Hand Off to Bracken

Kraken strands reads at the shared genus when species share k-mers; Bracken redistributes them down using genome-derived priors. It fixes the wrong-rank problem only - never genome-size bias, and never false positives (it can amplify or even invent a species by reassigning an absent organism's reads to its nearest congener). Run FP control first. Command mechanics live in abundance-estimation:

```bash
bracken -d "$KRAKEN_DB" -i out.kreport -o out.bracken -w out.bracken.kreport \
    -r 150 \   # MUST match a built databaseRLENmers.kmer_distrib AND the actual read length
    -l S -t 10 # species level; -t is a redistribution floor (drops taxa with fewer than 10 clade-level reads, strict <), not a confidence
```

## Per-Method Failure Modes

### Over-classification at default confidence
**Trigger:** running `--confidence 0` and reporting the species list. **Mechanism:** one shared k-mer can classify a read; the LCA labels it with its nearest database relative. **Symptom:** hundreds of low-abundance species, many biologically implausible. **Fix:** `--confidence 0.1-0.4` (database-dependent) plus `--minimum-hit-groups >=2`; verify the tail with unique minimizers.

### Counts read as abundance
**Trigger:** using the `.kreport` percentage column as relative abundance. **Mechanism:** read count is proportional to abundance x genome length x copy number. **Symptom:** large-genome taxa overstated; downstream diversity/ordination on a non-cell-fraction. **Fix:** run Bracken for the rank problem; treat even Bracken `fraction_total_reads` as a read fraction and hand off genome-size/copy-number caveats to abundance-estimation.

### Bracken read-length mismatch
**Trigger:** `-r 100` on 150 bp reads, or a database built only for a different length. **Mechanism:** the redistribution model is fragment-length specific. **Symptom:** biased abundances with no error (silent) if the `.kmer_distrib` exists, hard crash if it does not. **Fix:** `-r` = actual read length AND a matching `databaseRLENmers.kmer_distrib` must exist (build it or pick a prebuilt database shipping that length).

### Capped database plus high confidence
**Trigger:** a Standard-8/16 database with confidence cranked up. **Mechanism:** capped databases are random k-mer subsamples; few reads can clear a high threshold. **Symptom:** classification collapses toward zero; "my sample is mostly novel." **Fix:** use a full/large database for high confidence, or lower confidence on a capped database and accept lower precision.

### Host reads and contaminated references
**Trigger:** classifying without host depletion, then trusting human and low-level hits. **Mechanism:** host reads dominate low-biomass samples, and >2 million GenBank entries carry mislabeled human/vector sequence (Steinegger & Salzberg 2020 *Genome Biol* 21:115). **Symptom:** confident `Homo sapiens` plus a long artifactual tail. **Fix:** include `human` in the database and/or host-deplete upstream; scrutinize any taxon co-varying with host load; consider Recentrifuge negative-control subtraction.

## Quantitative Thresholds

| Threshold | Source | Rationale |
|-----------|--------|-----------|
| `--confidence` 0.0 default; use 0.2-0.4 on a comprehensive DB | Liu 2024 *aBIOTECH* 5:465; Lu 2022 *Nat Protoc* 17:2815 | species precision rose from ~0.16 to ~0.76 at CS 0.2; default over-classifies |
| `--minimum-hit-groups` 2 (raise to 3 for clinical) | Kraken2 manual | a single lucky minimizer/collision cannot make a call |
| Bracken `-k` = 35 | Lu 2017 *PeerJ Comput Sci* 3:e104 | must equal the Kraken2 database k-mer length |
| Bracken `-r` = actual read length | Bracken docs | redistribution priors are fragment-length specific |
| Bracken `-t` 10 default | Bracken docs | redistribution floor; too high deletes real rare taxa, not a confidence |
| Classification rate 30-70% (environmental) | community | low rate = novel taxa OR host contamination OR wrong database - diagnose which |
| Build k/l/s = 35/31/7 (nuc); 15/12/0 (prot) | Kraken2 manual | build-time only; cannot change k at classify time |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| Hundreds of implausible species | `--confidence 0`, no hit-group floor | raise confidence; `--minimum-hit-groups >=2`; unique-k-mer filter |
| Bracken: "kmer_distrib file not found" | `-r` has no matching built distribution | run `bracken-build -l <readlen>` or use a prebuilt DB shipping that length |
| Report parsing columns misaligned | `--report-minimizer-data` inserted 2 columns | parse 8-column layout when the flag is on |
| Near-zero classification on a small DB | capped (downsampled) DB + high confidence | larger DB, or lower confidence on the capped DB |
| Confident human + odd tail | host reads + contaminated references | host-deplete first; treat human/tail as suspect |
| Bash example silently truncates flags | inline `# comment` after a `\` line continuation | put comments on their own line |

## References

- Wood DE, Lu J, Langmead B. 2019. Improved metagenomic analysis with Kraken 2. *Genome Biol* 20:257.
- Wood DE, Salzberg SL. 2014. Kraken: ultrafast metagenomic sequence classification using exact alignments. *Genome Biol* 15:R46.
- Lu J, Breitwieser FP, Thielen P, Salzberg SL. 2017. Bracken: estimating species abundance in metagenomics data. *PeerJ Comput Sci* 3:e104.
- Breitwieser FP, Baker DN, Salzberg SL. 2018. KrakenUniq: confident and fast metagenomics classification using unique k-mer counts. *Genome Biol* 19:198.
- Lu J, Rincon N, Wood DE, Breitwieser FP, Pockrandt C, Langmead B, Salzberg SL, Steinegger M. 2022. Metagenome analysis using the Kraken software suite. *Nat Protoc* 17:2815-2839.
- Liu Y, Ghaffari MH, Ma T, Tu Y. 2024. Impact of database choice and confidence score on the performance of taxonomic classification using Kraken2. *aBIOTECH* 5:465-475.
- Steinegger M, Salzberg SL. 2020. Terminating contamination: large-scale search identifies more than 2,000,000 contaminated entries in GenBank. *Genome Biol* 21:115.
- Shen W, Xiang H, Huang T, et al. 2023. KMCP: accurate metagenomic profiling of both prokaryotic and viral populations by pseudo-mapping. *Bioinformatics* 39:btac845.

## Related Skills

- abundance-estimation - Bracken command mechanics and read-count-to-abundance conversion
- metaphlan-profiling - Marker-gene alternative; FP-conservative, abundance reported directly
- metagenome-visualization - Plot and run community stats on the resulting profiles
- contamination-controls - Host depletion, blanks, and decontam before classification
- genome-assembly/metagenome-assembly - Assembly/MAG recovery; this category is read-based
- read-qc/contamination-screening - Host/vector read screening before classification
- workflows/metagenomics-pipeline - End-to-end shotgun profiling

## Usage Guide

# Kraken Classification - Usage Guide

## Overview
Kraken2 assigns shotgun reads to taxa by matching their k-mers to a reference database via lowest-common-ancestor, using minimizers and a compact probabilistic hash (not exact k-mers). It is fast and sensitive, but its output is a database-conditioned similarity ledger: what each read most resembles in the chosen database, not a verified inventory and not an abundance. Useful results come from tuning three things - the database, the confidence threshold, and false-positive control - and from always re-estimating abundance with Bracken.

## Prerequisites
```bash
conda install -c bioconda kraken2 bracken krakentools

# Download a prebuilt database (sizes range from ~8 GB capped to ~70 GB Standard to ~480 GB nt)
wget https://genome-idx.s3.amazonaws.com/kraken/k2_standard_20240605.tar.gz
mkdir kraken2_db && tar -xzf k2_standard_20240605.tar.gz -C kraken2_db
```

Conceptual prerequisites:
- The database defines what can be detected. Standard = bacteria/archaea/viral/plasmid/human/UniVec; PlusPF adds protozoa/fungi; PlusPFP adds plant; nt is broadest but slowest and most contamination-prone; GTDB is curated. Capped 8/16 GB databases are random k-mer downsamples, not curated subsets.
- Remove host reads before or during classification (include `human` in the database, or pre-deplete). Host reads dominate low-biomass samples.
- Prebuilt databases ship matching Bracken distributions (typically 100/150/200mers). Bracken `-r` must match both the database and the actual read length.

## Quick Start
Tell your AI agent what you want to do:
- "Classify my shotgun reads with Kraken2 and the Standard database, with a confidence threshold"
- "Run Kraken2 on paired-end reads and re-estimate species abundance with Bracken at read length 150"
- "Check whether my low-abundance hits are real using unique k-mer counts"
- "Remove human reads before classifying my stool metagenome"

## Example Prompts

### Choosing a database and confidence
> "I have paired-end gut metagenome reads at 150 bp. Run Kraken2 with the PlusPF database, set confidence to suppress single-k-mer false positives, require at least two hit groups, then re-estimate species abundance with Bracken at read length 150."

### False-positive control for low biomass
> "This is a low-biomass clinical sample. Classify with high confidence, report distinct minimizer counts, and flag any species that has many reads but few distinct minimizers as a likely false positive."

### Host removal first
> "These are human stool shotgun reads. Remove human reads against a T2T reference before classifying, then profile with Kraken2 and the Standard database."

### Diagnosing a low classification rate
> "Only 25% of my reads classified. Help me decide whether that means novel taxa, host contamination, or the wrong database."

## What the Agent Will Do
1. Confirm the Kraken2 and Bracken versions, the database build, and the matching Bracken read length.
2. Recommend (or apply) host removal if the reads are not host-depleted.
3. Run classification with a non-default confidence and `--minimum-hit-groups`, producing a `.kreport`.
4. Apply false-positive control (unique minimizers / KrakenUniq) on tail taxa when biomass is low.
5. Re-estimate abundance with Bracken at the correct read length and level.
6. State explicitly that Bracken `fraction_total_reads` is a read fraction, not a cell fraction, and hand off genome-size caveats to abundance-estimation.

## Tips
- Default `--confidence 0` over-classifies by design; raise it. On a capped database, high confidence collapses classification toward zero - use a larger database instead.
- `--minimum-hit-groups 2` is a cheap precision lever the defaults rarely advertise; raise to 3 for clinical samples.
- A taxon at the bottom of the report is a hypothesis. Confirm it with distinct minimizers or KrakenUniq before believing it.
- Bracken never removes false positives; run confidence, hit-groups, and unique-k-mer filtering first.
- A low classification rate can mean novel taxa, host contamination, or the wrong database - diagnose which rather than assuming novelty.

## Output Files

| File | Description |
|------|-------------|
| out.kraken | Per-read classifications (large; can be dropped to /dev/null) |
| out.kreport | Taxonomic report that feeds Bracken |
| out.bracken | Bracken abundance table (read fractions) |

## Related Skills

- abundance-estimation - Bracken command mechanics and read-count-to-abundance conversion
- metaphlan-profiling - Marker-gene alternative; FP-conservative
- metagenome-visualization - Plot and run community stats on profiles
- contamination-controls - Host depletion, blanks, and decontam before classification
- genome-assembly/metagenome-assembly - Assembly/MAG recovery; this category is read-based
- read-qc/contamination-screening - Host/vector read screening before classification
- workflows/metagenomics-pipeline - End-to-end shotgun profiling

## Resources
- [Kraken2 GitHub](https://github.com/DerrickWood/kraken2)
- [Prebuilt databases](https://benlangmead.github.io/aws-indexes/k2)
- [Bracken GitHub](https://github.com/jenniferlu717/Bracken)

## Bundled Files

- `metagenomics--kraken-classification--examples--kraken2_classify.sh` — copied from `examples/kraken2_classify.sh`
