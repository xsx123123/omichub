# bio-epidemiological-genomics-amr-surveillance

> Bundled component reference for `epidemiological-genomics/amr-surveillance` (original source: `skills/bio_skills/epidemiological-genomics/amr-surveillance`).

Detects acquired antimicrobial-resistance determinants and chromosomal point-mutation resistance in bacterial assemblies using AMRFinderPlus, ResFinder 4.0 (acquired + PointFinder), CARD-RGI, abritAMR, staramr, and species-specific callers (TB-Profiler, Mykrobe). Harmonises cross-tool output via hAMRonization, contextualises determinants with mobile-genetic-element annotation (MOB-suite, PlasmidFinder, MobileElementFinder, ICEberg), predicts phenotype against EUCAST or CLSI breakpoints, and translates calls into WHO GLASS reporting categories. Use when screening clinical or surveillance isolates for AMR, distinguishing acquired vs intrinsic vs point-mutation resistance, calling rpoB / katG / pncA / gyrA / mgrB mutations, reconciling AMRFinderPlus vs RGI vs ResFinder disagreement, contextualising carbapenemases or mcr alleles on plasmids, predicting susceptibility from genotype against the WHO Mtb 2nd-edition catalogue, or building a hAMRonized multi-lab AMR surveillance pipeline.

## Instructions

## Version Compatibility

Reference examples tested with: ncbi-amrfinderplus 4.0+, resfinder 4.5+, rgi 6.0+ (CARD 3.3+), abritamr 1.0.14+, staramr 0.10+, hamronization 1.1+, tb-profiler 6.2+, mykrobe 0.13+, mob_suite 3.1+, plasmidfinder 2.1+, MobileElementFinder 1.0+, pandas 2.2+, BioPython 1.84+.

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- CLI: `<tool> --version` then `<tool> --help` to confirm flags
- AMRFinderPlus: `amrfinder --list_organisms` for the current `--organism` catalogue
- WHO Mtb catalogue: `tb-profiler list_db` and verify the bundled WHO edition
- AMR database freshness: `amrfinder -u` (NCBI ReferenceGeneCatalog) and `tb-profiler update_tbdb`

If a flag or column name does not match (`--species` vs `--organism`, `barcode_build` vs `barcode-build`), introspect the installed package rather than retrying. AMRFinderPlus, RGI, and ResFinder all renamed columns between major releases.

# AMR Surveillance

**"What antibiotic-resistance determinants are in this assembly, and what susceptibility do they imply?"** -> Combine acquired-gene detection, chromosomal point-mutation calling, mobile-element context, and curated phenotype mapping into a single per-isolate report fit for surveillance or clinical handover. Tool choice is determined by species (Mtb needs TB-Profiler, not AMRFinderPlus), reporting standard (WHO GLASS vs CARD vs in-house), and whether mobility matters (carbapenemase outbreak: yes; routine ESBL screen: less so).

- CLI: `amrfinder -n assembly.fa --organism Klebsiella_pneumoniae --plus` -- acquired + intrinsic-aware point mutations
- CLI: `tb-profiler profile -1 r1.fq.gz -2 r2.fq.gz -p sample` -- TB drug-resistance against WHO 2nd-edition catalogue
- CLI: `hamronize amrfinderplus --analysis_software_version 4.0.3 --reference_database_version 2025-02-01.1 in.tsv > out.tsv` -- normalise output across tools
- Python: `pandas` to join AMRFinderPlus + RGI + ResFinder + MOB-suite per-isolate for a single decision table

## The Single Most Important Modern Insight -- Acquired AMR detection is not species-agnostic

A pan-species AMRFinderPlus run misses chromosomal point-mutation resistance because the point-mutation panels are species-specific and activated only when `--organism` is set. Running `amrfinder -n mtb.fa` without `--organism` returns "no AMR detected" on an XDR-TB genome because AMRFinderPlus has no Mtb organism mode -- the user must switch tools (TB-Profiler or Mykrobe + WHO 2nd-edition catalogue). Similarly, *Salmonella* gyrA T83I, *Klebsiella* mgrB inactivation, and *E. coli* QRDR mutations are silent without `--organism Salmonella` / `Klebsiella_pneumoniae` / `Escherichia`. For any cross-tool surveillance pipeline, AMRFinderPlus with `--organism` MUST be paired with a species-specific second tool (TB-Profiler for Mtb; ResFinder 4.0 with `-s 'species'` for PointFinder coverage; hAMRonization to merge). Andersson et al. *Nat Rev Microbiol* 17:479 (2019) further notes that heteroresistance at 0.1-1% allele frequency is widespread and invisible to default variant callers, compounding the failure mode for any single-tool workflow.

## Algorithmic Taxonomy

| Tool | Mechanism | Inputs | Output | Strength | Fails when |
|------|-----------|--------|--------|----------|------------|
| AMRFinderPlus (Feldgarden 2021 *Sci Rep* 11:12728) | Curated HMM + BLAST against NCBI ReferenceGeneCatalog; per-gene cutoffs | assembly or protein | gene + class + element-type | Gene-family-aware (catches divergent variants); built-in species point-mutation panels | No Mtb mode; reports intrinsic genes unless `--organism` set |
| ResFinder 4.0 (Bortolaia 2020 *J Antimicrob Chemother* 75:3491) | BLAST against ResFinder DB (acquired) + PointFinder DB (chromosomal mutations) per species | assembly or reads | gene + predicted phenotype (S/I/R) | Phenotype prediction tied to CLSI/EUCAST | Requires explicit `-s 'species'` for PointFinder; default 90/60 cutoffs hide divergent variants |
| CARD-RGI (Alcock 2023 *NAR* 51:D690) | BLAST + HMM against CARD; tiers Perfect / Strict / Loose | assembly or protein | ARO ontology term, model-type (homolog / variant / overexpression / knockout / rRNA) | Mechanism-resolved (operons modelled); ARO ontology is curated | Loose tier produces many false positives; default Strict+Perfect misses real variants in non-model organisms |
| abritAMR (Sherry 2023 *Nat Commun* 14:60) | AMRFinderPlus wrapper + drug-class classifier; ISO-certified for clinical use | assembly | gene + drug class | First ISO-certified AMR pipeline; accredited reporting categories | Limited to AMRFinderPlus's underlying gene panel |
| staramr | ResFinder + PointFinder + PlasmidFinder + MLST in one pipeline | assembly | combined report | One-shot Salmonella / E. coli / Campylobacter surveillance | Default organism handling can hide point mutations; verify each component version |
| TB-Profiler (Phelan 2019 *Genome Med* 11:41) | Maps reads or assembly against H37Rv + WHO catalogue + Coll/Napier lineage barcode | reads or assembly | per-drug R/R-interim/Uncertain/S + lineage | WHO 2nd-edition catalogue integration; lineage call; heteroresistance from allele frequency | Hardcoded to MTBC; older bundled DB may predate current WHO edition |
| Mykrobe (Hunt 2019 *Wellcome Open Res* 4:191) | k-mer presence/absence against curated panel | reads | species + AMR per drug | k-mer-fast; cross-checks TB-Profiler; supports Mtb, S. aureus, Salmonella, gonorrhoea | Panel may lag WHO catalogue; check `--panel` |
| hAMRonization (PHA4GE) | Format converter to PHA4GE schema | per-tool TSV | unified TSV/JSON | Cross-tool comparison; surveillance harmonisation | Mandatory metadata fields differ per tool subparser |

## Decision Tree by Scenario

| Scenario | Recommended | Why wrong choices fail |
|----------|-------------|------------------------|
| Routine screen of an *E. coli* / *Klebsiella* / *Salmonella* assembly for acquired AMR + point mutations | AMRFinderPlus with `--organism Escherichia` / `Klebsiella_pneumoniae` / `Salmonella` + `--plus` | Without `--organism`: no PointFinder panel, fluoroquinolone QRDR mutations missed; intrinsic-gene noise in Klebsiella |
| *M. tuberculosis* drug-resistance prediction | TB-Profiler interpreted via WHO 2nd-edition catalogue, Mykrobe as cross-check on R/XDR isolates | AMRFinderPlus has no Mtb organism mode; ResFinder PointFinder lacks the full WHO catalogue; tool defaults silently call Group 3 mutations as "susceptible" |
| Predict S/I/R phenotype, not gene presence | ResFinder 4.0 OR abritAMR; document EUCAST or CLSI breakpoint year | AMRFinderPlus reports presence only; mapping presence -> phenotype needs curated rules |
| Carbapenemase outbreak: is the gene mobile? | AMRFinderPlus -> MOB-suite (`mob_recon` + `mob_typer`) -> cross-reference; long-read or hybrid assembly recommended | PlasmidFinder alone gives replicon type but not gene-plasmid linkage; short-read draft assemblies fragment plasmid contigs and lose context |
| Cross-laboratory surveillance reporting | Pass per-tool output through hAMRonization to PHA4GE schema; populate `analysis_software_version` and `reference_database_version` | Raw cross-tool comparison is meaningless (CARD ARO vs ResFinder name vs NCBI ReferenceGeneCatalog) |
| Novel-variant surveillance (emergence) | AMRFinderPlus (HMM, gene-family-aware) OR CARD-RGI with Loose-tier manual review | abricate's 80/80 defaults reject divergent family members; pure-BLAST defaults silently miss novel mcr / OXA sub-variants |
| Quantitative AMR from metagenomic reads | AMRPlusPlus / DeepARG / ARGs-OAP normalised to 16S; report "ARG abundance" NOT "resistance" | Assembly-based tools fail on short reads; reporting environmental ARG counts as "resistance" inherits the environmental-resistome critique that homolog presence is not phenotypic resistance |
| Colistin resistance in *Klebsiella* / *Enterobacter* / *Salmonella* | mcr-1 to mcr-10 acquired (AMRFinderPlus; mcr-1 originally Liu 2016 *Lancet Infect Dis* 16:161) + mgrB / pmrAB / phoPQ point mutations (`--organism Klebsiella_pneumoniae`) + phenotypic confirmation for mcr-9/10 | mcr-9 / mcr-10 frequently report without elevated MIC; treating mcr presence as "colistin-R" triggers infection control unnecessarily |
| WHO GLASS submission | hAMRonization -> drug-class mapping -> EUCAST/CLSI breakpoint interpretation; record breakpoint year | Gene-level reporting without class mapping cannot populate GLASS categories |

Methodology evolves rapidly; before a high-stakes outbreak report, web-search "AMRFinderPlus organism modes 2026" and confirm the WHO Mtb catalogue edition currently bundled in TB-Profiler.

## AMRFinderPlus With Species Mode

**Goal:** Produce a per-isolate AMR report including acquired genes, species-specific chromosomal point mutations, stress/virulence elements, and per-hit method and coverage metadata for downstream harmonisation.

**Approach:** Run `amrfinder` with `-n` for nucleotide assembly, `--organism` to activate the species-specific point-mutation panel, `--plus` to include stress / virulence / heat / metal, and `--report_all` when truncated-gene visibility matters. Pin the database via `amrfinder -u` -> verify `--db` matches a recorded date.

```bash
DB=$(amrfinder -V | grep -i database | awk '{print $NF}')

amrfinder \
    -n assembly.fa \
    --organism Klebsiella_pneumoniae \
    --plus \
    --threads 8 \
    -o sample.amrfinder.tsv

echo "DB version: ${DB}" >> sample.amrfinder.tsv
```

Column semantics worth inspecting: `Element type` (AMR / POINT / VIRULENCE / STRESS / etc.), `Method` (EXACTX / PARTIAL_CONTIG_END / HMM / etc. -- partial-contig hits flag assembly fragmentation), `% Coverage of reference sequence`, `% Identity to reference sequence`, `Class` / `Subclass` (drug-class summary). `Method = PARTIAL_CONTIG_END` is the smoking gun for plasmid-context fragmentation -- consider long-read confirmation.

## TB-Specific Workflow

**Goal:** Generate a WHO-catalogue-aligned drug-resistance report for *M. tuberculosis* covering all 13 first-line + second-line + new/repurposed drugs, with lineage assignment via the Coll/Napier MTBC barcode (90-SNP version) and explicit handling of Group 3 (Uncertain) mutations.

**Approach:** TB-Profiler primary (it bundles the WHO catalogue and reports the Walker 2022 / 2023 association grouping); Mykrobe as an orthogonal cross-check on any R / XDR call that will drive treatment. NEVER collapse Group 3 mutations to "susceptible" -- the WHO catalogue's tiered scoring is load-bearing for clinical handover.

```bash
tb-profiler update_tbdb

tb-profiler profile \
    -1 reads_R1.fq.gz \
    -2 reads_R2.fq.gz \
    -p sample \
    --txt --csv --pdf \
    --dir tbprofiler_out

mykrobe predict \
    --sample sample \
    --species tb \
    --output sample.mykrobe.json \
    --format json \
    reads_R1.fq.gz reads_R2.fq.gz
```

Allix-Béguec et al. (CRyPTIC) *NEJM* 379:1403 (2018) established >99% negative predictive value for first-line drugs and is the basis for WGS-only DST policies; the same study showed sensitivity remains lower for bedaquiline, delamanid, linezolid, and clofazimine, so phenotypic DST is still required for second-line and new/repurposed agents in MDR/XDR-TB workups. The WHO 2023 catalogue (Walker et al. *Lancet Microbe* 3:e265, 2022 for the 2021 edition methodology; 2023 second edition data) grades each mutation **Group 1** / **Group 2** (Associated -- interim) / **Group 3** (Uncertain) / **Group 4** (Not Associated -- interim) / **Group 5** (Not Associated). Reporting Group 3 as "S" actively misleads clinicians.

## hAMRonization for Cross-Tool Reporting

**Goal:** Convert per-tool AMR output (AMRFinderPlus, ResFinder, RGI, abricate, staramr, ARIBA, TB-Profiler, Mykrobe) to the PHA4GE schema so a multi-laboratory or multi-tool surveillance dataset is comparable.

**Approach:** Invoke `hamronize <tool>` per input with mandatory provenance metadata (`--analysis_software_version`, `--reference_database_version`, `--input_file_name`), then `hamronize summarize` to merge.

```bash
hamronize amrfinderplus \
    --analysis_software_version 4.0.3 \
    --reference_database_version 2025-02-01.1 \
    --input_file_name sample.amrfinder.tsv \
    sample.amrfinder.tsv > sample.hamr.tsv

hamronize resfinder \
    --analysis_software_version 4.5.0 \
    --reference_database_version 2024-12-15 \
    --input_file_name sample.resfinder.json \
    sample.resfinder.json > sample.resfinder.hamr.tsv

hamronize summarize -t tsv -o cohort.hamr.tsv per_sample_hamr/*.tsv
```

Default reporting ontology for public-health output is NCBI ReferenceGeneCatalog. Two consequences: (1) CARD ARO terms need translation; (2) any custom gene additions need a corresponding NCBI accession before they appear in the harmonised stream.

## Mobile-Genetic-Element Context

**Goal:** Determine whether a clinically actionable AMR gene (carbapenemase, mcr, ESBL) sits on a chromosome, a plasmid (and which incompatibility group / cluster), an integrative-conjugative element, or a transposon -- because "gene present" tells the infection-control team nothing about transmissibility.

**Approach:** Reconstruct plasmids from the assembly with MOB-suite `mob_recon`; type each plasmid with `mob_typer`; cross-reference AMR-gene coordinates against the plasmid contig list; annotate IS elements / integrons with MobileElementFinder. For surveillance-grade plasmid resolution, prefer long-read (R10.4.1 Q20+) or hybrid assemblies -- short-read draft assemblies routinely fragment plasmid contigs.

```bash
mob_recon \
    --infile assembly.fa \
    --outdir mob_out/ \
    --num_threads 4

mob_typer \
    --infile mob_out/plasmid_AA001.fasta \
    --out_file mob_out/plasmid_AA001.typed.tsv

mefinder find \
    --contig assembly.fa \
    --out mef_out/sample \
    --threads 4
```

Document MOB-suite version explicitly: v2 and v3 cluster codes are non-interoperable, and v3.1+ adds MGE reporting. Across longitudinal surveillance crossing the v2 -> v3 boundary, the same plasmid receives different cluster IDs and appears spuriously "novel".

## Per-Method Failure Modes

### AMRFinderPlus run pan-species on a *Mycobacterium tuberculosis* assembly

**Trigger:** `amrfinder -n mtb.fa` without `--organism`; AMRFinderPlus has no Mtb organism mode in any v4.x release.

**Mechanism:** The species-specific point-mutation panels are activated only when a recognised `--organism` is passed. Mtb resistance is overwhelmingly chromosomal point mutation (rpoB / katG / inhA / pncA / embB / gyrA / rrs). With no panel active, none of these are called.

**Symptom:** Empty AMR table on a phenotypically MDR/XDR isolate; lineage barcode not reported (AMRFinderPlus does not call MTBC lineage).

**Fix:** Switch tools. Use TB-Profiler (preferred -- bundles WHO catalogue + Coll/Napier barcode) or Mykrobe; the AMRFinderPlus catalogue does not cover MTBC.

### OXA-48-like family collapsed to a single bucket

**Trigger:** Default per-isolate summarisers report the gene family (`bla_OXA-48-like`) rather than the allele (`bla_OXA-244`).

**Mechanism:** OXA-48 (potent carbapenemase), OXA-181 (Thr213Ala -- similar activity, different plasmid), OXA-232 (Arg214Ser -- reduced carbapenemase activity), and OXA-244 (Arg214Gly -- weakest, often phenotypically susceptible to ertapenem) share >95% identity. Pipelines that report family-level summary erase the clinically actionable variant identity.

**Symptom:** Surveillance report says "OXA-48-like detected", phenotype is borderline ertapenem-susceptible / meropenem-susceptible, clinical team is confused about whether ceftazidime-avibactam is needed.

**Fix:** Report the allele explicitly; never collapse to family. AMRFinderPlus reports the allele in `Gene symbol` -- preserve it through hAMRonization rather than summarising.

### IS-element-mediated derepression invisible to gene-presence pipelines

**Trigger:** Phenotypic high-level AmpC hyperproduction in *Enterobacter cloacae* complex / *Citrobacter freundii*; or KPC over-expression on Tn4401b (100-bp promoter deletion).

**Mechanism:** Resistance is mediated by IS*Ecp1* / IS*26* / IS*10* insertion upstream of the ampC promoter producing a strong hybrid promoter, or by Tn4401 variant. Gene presence is unchanged. Short-read assemblies fragment IS elements and collapse repeats; promoter context is lost. AMRFinderPlus / RGI / ResFinder report the gene; the regulatory configuration is not annotated.

**Symptom:** AMR pipeline output identical for wild-type ampC carrier and the hyperproducer; clinical phenotype is divergent.

**Fix:** Long-read (Nanopore R10.4.1 Q20+ or PacBio HiFi) or hybrid assembly with explicit promoter-context inspection. For Tn4401 variant typing, manual blast of the transposon region. Tools that automate this are emerging but not yet a default in surveillance pipelines.

### Heteroresistance below default variant-caller thresholds

**Trigger:** Routine Illumina WGS-AMR pipeline on a clinical isolate; resistance variant appears at 1-5% allele frequency.

**Mechanism:** Heteroresistance -- clonal subpopulations carrying resistance at 0.1-1% (Andersson, Nicoloff, Hjort *Nat Rev Microbiol* 17:479, 2019) -- is widespread and clinically meaningful (treatment failure under antibiotic pressure). Default variant callers (`bcftools`, `lofreq` default `-q 20`, GATK HaplotypeCaller) require minor-allele frequency of typically 10-20% to call. Assembly-based pipelines (AMRFinderPlus on assembly) collapse minor variants entirely.

**Symptom:** Surveillance pipeline calls "S" but clinical failure under therapy; subsequent sampling reveals high-level resistance.

**Fix:** For clinically critical drugs, supplement assembly-based AMR with deep-read variant calling at lower MAF thresholds (`lofreq` with `-q 13 -a 0.01`), or use targeted deep-amplicon sequencing. TB-Profiler reports allele frequency for resistance calls -- inspect for heteroresistance routinely.

### WHO Mtb Group 3 mutations silently called "susceptible"

**Trigger:** TB-Profiler / Mykrobe run on an Mtb isolate carrying a mutation graded Group 3 (Uncertain) in the WHO catalogue.

**Mechanism:** Tools translate Group 3 calls to "no resistance prediction" in their summary; downstream summarisers and clinical handover forms collapse "no prediction" to "S". The Walker 2022 *Lancet Microbe* catalogue methodology explicitly separates Group 3 (Uncertain) from Group 4/5 (Not Associated) for exactly this reason.

**Symptom:** Patient treated as drug-susceptible; clinical failure; retrospective inspection finds Group 3 mutation that should have triggered phenotypic DST.

**Fix:** Read TB-Profiler JSON output, NOT the simplified TSV. Report Group 3 mutations explicitly with "uncertain significance -- phenotypic DST recommended". This is widely under-communicated in surveillance pipelines.

### fosA / efflux-regulator hits overcalled as resistance

**Trigger:** Chromosomal fosA in *Klebsiella pneumoniae* / *Enterobacter* / *Serratia* reported as "fosfomycin resistant" by ResFinder / AMRFinderPlus.

**Mechanism:** Chromosomal fosA confers low-level fosfomycin resistance below the EUCAST clinical breakpoint (32 mg/L for urinary isolates). Treating chromosomal-fosA *E. coli* as fosfomycin-resistant withholds an oral option for uncomplicated UTI unnecessarily.

**Symptom:** All *K. pneumoniae* isolates flagged "fosfomycin-R" regardless of plasmid context or phenotype.

**Fix:** AMRFinderPlus with `--organism Klebsiella_pneumoniae` suppresses the intrinsic fosA report; verify the suppression worked. Cross-reference fosA hits with MOB-suite to determine plasmid context; only plasmid-borne or upregulated fosA should be reported as resistance.

## Reconciliation: When AMR Tools Disagree

| Pattern | Likely cause | Action |
|---------|--------------|--------|
| AMRFinderPlus calls `bla_NDM-5`; ResFinder calls `bla_NDM-1` | Allele assignment differs by reference database (NCBI ReferenceGeneCatalog vs ResFinder DB); both are within the NDM family | Report the family + flag the allele discordance; for clinical handover prefer NCBI nomenclature, for legacy comparability prefer ResFinder |
| RGI calls `mecA` "Strict"; AMRFinderPlus calls "EXACTX" | Tier semantics differ; both real hits | Concordant resistance call -- harmonise via hAMRonization, use NCBI ReferenceGeneCatalog nomenclature |
| ResFinder reports a gene at 88% identity; AMRFinderPlus omits | ResFinder default 90/60; AMRFinderPlus HMM cutoff stricter for that family | Manual review; for novel-variant surveillance, AMRFinderPlus + Loose-tier RGI catches more |
| TB-Profiler and Mykrobe disagree on isoniazid | Different curated panels; one may predate WHO 2nd edition | Defer to TB-Profiler interpreted against WHO catalogue; manual blast of katG / inhA / fabG1 |
| mcr-9 detected; phenotypic colistin MIC susceptible | Expected -- mcr-9 frequently silent without IqrR / induction | Report mcr-9 detection + susceptibility; do NOT trigger infection-control as if MCR-1 |
| AMRFinderPlus `Method=PARTIAL_CONTIG_END` for a carbapenemase | Assembly fragmentation at the plasmid edge | Re-assemble with long reads or hybrid before reporting; the gene may be present in full |
| RGI calls a long list of "Loose" hits | Non-model organism or distant lineage | Manual curation of Loose hits -- discard generic homologs, retain those near canonical AMR-active residues |

## Quantitative Thresholds

| Quantity | Threshold | Source / rationale |
|----------|-----------|--------------------|
| AMRFinderPlus default %identity | per-gene curated (typically 90% global) | Feldgarden 2021 *Sci Rep* 11:12728; HMM cutoff is gene-family-aware |
| AMRFinderPlus default %coverage | 50% (alignment coverage) | NCBI Reference; `--report_all` exposes partial hits |
| ResFinder default %id / %coverage | 90% / 60% | CGE convention; tighter than abricate |
| abricate default %id / %coverage | 80% / 80% | Too permissive for novel-variant surveillance |
| WHO Mtb Group 1 (Associated with R) | High-confidence resistance call | Walker 2022 *Lancet Microbe* 3:e265 |
| WHO Mtb Group 3 (Uncertain) | NOT "susceptible" -- phenotypic DST recommended | Walker 2022 *Lancet Microbe* 3:e265; 2023 2nd edition data |
| Heteroresistance MAF | 0.1-1% (deep amplicon detection) | Andersson 2019 *Nat Rev Microbiol* 17:479 |
| EUCAST fosfomycin urinary breakpoint | 32 mg/L | EUCAST clinical breakpoint tables (year-specific) |
| Variant MAF for routine WGS-AMR calling | 10% (`lofreq` default), 20% (GATK default) | Tool defaults; document per-pipeline |

## Common Errors

| Error / symptom | Cause | Solution |
|-----------------|-------|----------|
| AMRFinderPlus empty on TB assembly | No Mtb `--organism` mode | Switch to TB-Profiler / Mykrobe |
| AMRFinderPlus calls intrinsic fosA on Klebsiella | `--organism` not set; intrinsic suppression off | Always pass `--organism` for the species |
| `--species` flag rejected | AMRFinderPlus uses `--organism`, not `--species` | Use `--organism Klebsiella_pneumoniae` |
| Different gene names for same determinant across tools | CARD ARO vs ResFinder vs NCBI ReferenceGeneCatalog | Pass through `hamronize` |
| `Method=PARTIAL_CONTIG_END` on a clinically critical gene | Assembly fragmentation | Re-assemble with long reads / hybrid |
| `hamronize` rejects input as missing metadata | `--analysis_software_version` not supplied | Populate all mandatory PHA4GE fields per tool subparser |
| MOB-suite cluster codes don't match published outbreak paper | v2 vs v3 incompatibility | Re-run with matched MOB-suite version; document |
| Point-mutation panel coverage list flips between AMRFinderPlus minor releases | DB schema change | `amrfinder --list_organisms` and record the version |
| TB-Profiler bundled DB predates WHO 2nd edition | DB not updated | `tb-profiler update_tbdb` and verify catalogue edition |

## Anticipated Reviewer Pushback

| Pushback | Response |
|----------|----------|
| "Why AMRFinderPlus, not RGI?" | AMRFinderPlus uses gene-family HMMs and NCBI-curated cutoffs that catch divergent novel variants without producing the Loose-tier noise of RGI; both are valid and `hamronize` lets the reviewer compare |
| "How were Group 3 WHO Mtb mutations handled?" | Reported as "Uncertain significance -- phenotypic DST recommended"; not collapsed to S |
| "What about heteroresistance?" | Read-based deep variant calling supplements assembly-based AMR for clinically critical drugs; report MAF |
| "Why not just trust ResFinder phenotype prediction?" | EUCAST/CLSI breakpoint year must be documented; rule-based phenotype prediction inherits its curation as a hidden dependency. Pair with explicit gene + class reporting |
| "Why long-read assembly for AMR?" | Short-read drafts fragment plasmid contigs and lose MGE / promoter context (e.g., IS*Ecp1* upstream of ampC; Tn4401 variants); long-read or hybrid is mandatory for any mobility / regulatory claim |
| "Why hAMRonization rather than tool-native outputs?" | Cross-tool comparison requires schema unification; PHA4GE is the public-health consensus |
| "Was the intrinsic vs acquired distinction considered?" | Yes -- `--organism` activates suppression of clinically inert intrinsic genes; reported separately |

## References

- Feldgarden M, Brover V, Haft DH et al (2021) AMRFinderPlus and the Reference Gene Catalog facilitate examination of the genomic links among antimicrobial resistance, stress response, and virulence. *Sci Rep* 11:12728. doi:10.1038/s41598-021-91456-0
- Bortolaia V, Kaas RS, Ruppe E et al (2020) ResFinder 4.0 for predictions of phenotypes from genotypes. *J Antimicrob Chemother* 75(12):3491-3500. doi:10.1093/jac/dkaa345
- Alcock BP, Huynh W, Chalil R et al (2023) CARD 2023: expanded curation, support for machine learning, and resistome prediction at the Comprehensive Antibiotic Resistance Database. *Nucleic Acids Res* 51(D1):D690-D699. doi:10.1093/nar/gkac920
- Phelan JE, O'Sullivan DM, Machado D et al (2019) Integrating informatics tools and portable sequencing technology for rapid detection of resistance to anti-tuberculous drugs. *Genome Med* 11:41. doi:10.1186/s13073-019-0650-x
- Hunt M, Bradley P, Lapierre SG et al (2019) Antibiotic resistance prediction for Mycobacterium tuberculosis from genome sequence data with Mykrobe. *Wellcome Open Res* 4:191. doi:10.12688/wellcomeopenres.15603.1
- Walker TM et al (CRyPTIC / WHO) (2022) The 2021 WHO catalogue of Mycobacterium tuberculosis complex mutations associated with drug resistance: a genotypic analysis. *Lancet Microbe* 3(4):e265-e273. doi:10.1016/S2666-5247(21)00301-3
- Allix-Béguec C et al (CRyPTIC) (2018) Prediction of susceptibility to first-line tuberculosis drugs by DNA sequencing. *N Engl J Med* 379(15):1403-1415. doi:10.1056/NEJMoa1800474
- Robertson J, Nash JHE (2018) MOB-suite: software tools for clustering, reconstruction and typing of plasmids from draft assemblies. *Microb Genom* 4(8):e000206. doi:10.1099/mgen.0.000206
- Carattoli A, Zankari E, García-Fernández A et al (2014) In silico detection and typing of plasmids using PlasmidFinder and plasmid multilocus sequence typing. *Antimicrob Agents Chemother* 58(7):3895-3903. doi:10.1128/AAC.02412-14
- Johansson MHK, Bortolaia V, Tansirichaiya S et al (2021) Detection of mobile genetic elements associated with antibiotic resistance in Salmonella enterica using a newly developed web tool: MobileElementFinder. *J Antimicrob Chemother* 76(1):101-109. doi:10.1093/jac/dkaa390
- Sherry NL, Horan KA, Ballard SA et al (2023) An ISO-certified genomics workflow for identification and surveillance of antimicrobial resistance. *Nat Commun* 14:60. doi:10.1038/s41467-022-35713-4
- Andersson DI, Nicoloff H, Hjort K (2019) Mechanisms and clinical relevance of bacterial heteroresistance. *Nat Rev Microbiol* 17(8):479-496. doi:10.1038/s41579-019-0218-1
- Liu YY, Wang Y, Walsh TR et al (2016) Emergence of plasmid-mediated colistin resistance mechanism MCR-1 in animals and human beings in China. *Lancet Infect Dis* 16(2):161-168. doi:10.1016/S1473-3099(15)00424-7

## Related Skills

- pathogen-typing - Strain context for AMR (Kleborate, MLST, cgMLST) feeds clonal interpretation of resistance dissemination
- transmission-inference - Outbreak transmission inference for resistant clones uses AMR + cgMLST jointly
- variant-surveillance - Lineage-level AMR-prevalence tracking for SARS-CoV-2-style surveillance (drug-resistance mutations in antiviral context)
- metagenomics/amr-detection - Community AMR / ARG quantification (NOT isolate-focused)
- variant-calling/variant-calling - Per-isolate SNP calling that feeds point-mutation panels
- variant-calling/filtering-best-practices - MAF threshold discipline for heteroresistance detection
- long-read-sequencing/long-read-alignment - Plasmid / promoter-context resolution for MGE-aware AMR
- comparative-genomics/whole-genome-alignment - Reference-based coordinate handling for point mutations
- clinical-databases/pharmacogenomics - Adjacent (host-side) pharmacogenetics, distinct from pathogen AMR
- workflows/somatic-variant-pipeline - End-to-end orchestration patterns (analogous to outbreak-pipeline workflows)

## Usage Guide

# AMR Surveillance Usage Guide

## Overview

This skill drives postdoc-grade antimicrobial-resistance surveillance from bacterial WGS. It covers acquired AMR gene detection (AMRFinderPlus, ResFinder 4.0, CARD-RGI, abricate), chromosomal point-mutation calling (PointFinder, AMRFinderPlus species mode, TB-Profiler, Mykrobe), mobile-genetic-element context (MOB-suite, PlasmidFinder, MobileElementFinder), and phenotype prediction against EUCAST / CLSI breakpoints. Cross-tool reporting is harmonised through hAMRonization to the PHA4GE schema, and TB drug-resistance prediction is interpreted against the WHO 2nd-edition catalogue. The skill is decision-grade: it tells the agent when to switch from AMRFinderPlus to TB-Profiler, how to handle WHO Group 3 (Uncertain) calls without misleading clinicians, when heteroresistance demands deep read-based variant calling, and when to insist on long-read assembly for plasmid resolution.

Distinct from `metagenomics/amr-detection` (community-level ARG quantification, not isolate-focused) and from `variant-calling/variant-calling` (which owns SNP-calling mechanics that this skill consumes).

## Prerequisites

```bash
conda install -c bioconda ncbi-amrfinderplus resfinder rgi abricate hamronization abritamr staramr tb-profiler mykrobe mob_suite plasmidfinder mefinder lofreq snippy

amrfinder -u
tb-profiler update_tbdb

pip install pandas biopython
```

For long-read or hybrid assembly upstream:

```bash
conda install -c bioconda flye unicycler medaka
```

## Quick Start

Tell the AI agent what surveillance question to answer:

- "Detect acquired AMR genes and chromosomal point mutations in this Klebsiella pneumoniae assembly"
- "Predict drug-susceptibility phenotype against EUCAST 2024 breakpoints for these E. coli bloodstream isolates"
- "Run TB-Profiler against the WHO 2nd-edition catalogue and report per-drug resistance with Group 1/2/3/4/5 grading explicit"
- "Identify carbapenemase variants in these 40 hospital isolates and tell me which are plasmid-borne via MOB-suite"
- "Harmonise AMRFinderPlus + ResFinder + RGI output for 200 isolates via hAMRonization in PHA4GE format for WHO GLASS submission"
- "Screen these isolates for heteroresistance to colistin using deep read-based variant calling at 1% MAF"
- "Cross-check TB-Profiler and Mykrobe for any XDR-TB call before clinical handover"

## Example Prompts

### WGS-to-WHO-GLASS clinical surveillance report

> "We have 250 Illumina paired-end runs of clinical *E. coli* and *Klebsiella pneumoniae* from a tertiary hospital ICU surveillance project spanning Q1-Q4 2025. Assemble with Unicycler, run AMRFinderPlus with `--organism` set per isolate plus `--plus`, run ResFinder 4.0 with `--acquired --point -s 'species'`, harmonise via hAMRonization, and produce a long-format CSV mapping isolate -> antibiotic class -> highest-confidence determinant -> predicted phenotype, in WHO GLASS reporting categories (S / I / R / Insufficient evidence) against EUCAST 2025 breakpoints. Document every tool version and database date."

### Mobile-genetic-element context for an NDM-1 outbreak

> "Twenty *Klebsiella pneumoniae* isolates from a suspected NDM-1 outbreak across two wards. For each, identify the carbapenemase via AMRFinderPlus, reconstruct plasmid contigs via MOB-suite `mob_recon`, type each plasmid via `mob_typer`, check for IS*26* / IS*Kpn7* mobilisation via MobileElementFinder, and tell me whether the NDM-1-bearing plasmid is the same replicon and MOB-suite cluster across isolates. Recommend a long-read confirmation isolate if plasmid context appears fragmented in any short-read assembly (`Method=PARTIAL_CONTIG_END` in AMRFinderPlus output)."

### Mycobacterium tuberculosis drug-resistance prediction

> "Sixteen MTB clinical assemblies from a high-burden setting. Run TB-Profiler with the current WHO 2nd-edition catalogue; report per-drug resistance call (R / R-interim / Uncertain / S / Not predicted) for the 13 anti-TB drugs in the catalogue, flag Coll/Napier lineage assignment, and call out high-confidence rpoB / katG / pncA / gyrA / inhA mutations explicitly. Run Mykrobe as a cross-check on any R or XDR call. Do NOT collapse Group 3 (Uncertain) mutations to 'S' -- report them as 'phenotypic DST recommended'."

### Heteroresistance screen for colistin

> "Five *Klebsiella pneumoniae* clinical isolates with treatment failure on colistin. Run deep read-based variant calling with lofreq at MAF >= 1% across mgrB / pmrAB / phoPQ, report any non-reference allele frequency between 1% and 20% as heteroresistance candidates, and compare against the assembly-based AMRFinderPlus output. For any heteroresistance candidate flag for targeted deep amplicon sequencing."

### mcr surveillance with phenotypic context

> "Hundred isolates from a one-year colistin-resistance surveillance project across food-animal and clinical sources. Detect mcr-1 through mcr-10 acquired genes via AMRFinderPlus; for each mcr-9 and mcr-10 hit, flag that phenotypic colistin MIC confirmation is required before reporting as colistin-R. Cross-reference with MOB-suite to determine plasmid host-range. Produce a per-sample table: mcr variant, plasmid replicon, predicted host range, phenotypic confirmation status."

### Cross-tool reconciliation for a single isolate

> "I have AMRFinderPlus calling `bla_NDM-5`, ResFinder calling `bla_NDM-1`, and RGI calling `bla_NDM-1`. Pass everything through hAMRonization, reconcile against NCBI ReferenceGeneCatalog nomenclature, and tell me whether the discordance is real allele difference or database-naming drift. If real, explain the MIC implications."

## What the Agent Will Do

1. Identify the surveillance question (presence vs phenotype prediction vs MGE context vs heteroresistance vs cross-lab reporting) and the species.
2. Select the primary tool by the decision tree: AMRFinderPlus with `--organism` for *E. coli* / *Salmonella* / *Klebsiella* / *Staphylococcus* / etc.; TB-Profiler for *M. tuberculosis*; ResFinder 4.0 or abritAMR for phenotype prediction.
3. Pin tool versions AND database versions; record AMRFinderPlus DB date, TB-Profiler WHO catalogue edition, MOB-suite version.
4. For Mtb, run TB-Profiler primary + Mykrobe cross-check; interpret against WHO 2nd-edition catalogue; report Group 3 mutations as "uncertain significance".
5. For mobility claims, run MOB-suite `mob_recon` + `mob_typer` and recommend long-read confirmation if short-read assembly produces fragmented plasmid contigs (`Method=PARTIAL_CONTIG_END`).
6. For heteroresistance, supplement assembly-based calls with deep read-based variant calling (lofreq at MAF >= 1%) for clinically critical drugs.
7. Harmonise all per-tool output via `hamronize` with mandatory PHA4GE provenance metadata, then `hamronize summarize` for the cohort table.
8. Translate gene-level calls to drug-class -> EUCAST/CLSI breakpoint-year-anchored S/I/R; populate WHO GLASS categories.
9. Flag any reconciliation ambiguity (AMRFinderPlus vs ResFinder allele assignment, RGI tier semantics) for analyst review rather than silent resolution.

## Tips

- AMRFinderPlus has no Mtb organism mode in any v4.x release. Calling `amrfinder -n mtb.fa` returns an empty AMR table on an XDR-TB genome. Use TB-Profiler.
- WHO 2nd-edition catalogue (2023) supersedes the 2021 1st edition. The 3rd edition is anticipated late 2025-2026; check `tb-profiler list_db` for the bundled edition before clinical handover.
- Never report OXA-48-like at family level. The allele identity (OXA-48 vs OXA-181 vs OXA-232 vs OXA-244) determines whether ertapenem alone is elevated, whether ceftazidime-avibactam will work, and whether the strain looks phenotypically susceptible.
- `Method=PARTIAL_CONTIG_END` in AMRFinderPlus output is the smoking gun for plasmid-context fragmentation in short-read assembly. Re-assemble with long-read (Nanopore R10.4.1 Q20+ or PacBio HiFi) or hybrid before reporting MGE context.
- mcr-9 and mcr-10 frequently report without elevated MIC. Always require phenotypic confirmation before triggering infection-control as if mcr-1.
- AMRFinderPlus `--organism Klebsiella_pneumoniae` suppresses intrinsic-gene noise (fosA, oqxAB). Cross-organism comparisons that mix `--organism`-on with `--organism`-off output are not pooled-comparable.
- hAMRonization is mandatory for any multi-lab or multi-tool surveillance report. Raw AMRFinderPlus vs ResFinder vs RGI comparison is uninterpretable because of CARD ARO vs ResFinder vs NCBI ReferenceGeneCatalog ontology differences.
- For Tn4401 promoter variants (Tn4401a vs Tn4401b vs Tn4401d -- expression differences of ~5-fold), short-read pipelines cannot resolve the variant. Long-read confirmation required for any expression-level claim.
- EUCAST and CLSI breakpoint tables update annually. Document the breakpoint year alongside the S/I/R call -- a 2023-breakpoint "S" may be a 2025-breakpoint "I".
- For heteroresistance screening, default variant-caller MAF thresholds (10% lofreq, 20% GATK) hide the clinically relevant 0.1-1% subpopulations documented by Andersson et al. 2019. Use targeted deep amplicon sequencing or lofreq with `-q 13 -a 0.01`.
- MOB-suite v2 and v3 cluster codes are non-interoperable. Document version explicitly; v3.1+ adds MGE reporting. Longitudinal surveillance crossing the v2 -> v3 boundary requires re-running.

## Related Skills

- pathogen-typing - cgMLST / Kleborate / MLST for clonal context of AMR dissemination
- transmission-inference - SNP-cluster / outbreak transmission inference for resistant clones
- variant-surveillance - Lineage-level antiviral-drug-resistance tracking
- metagenomics/amr-detection - Community ARG quantification (not isolate AMR)
- variant-calling/variant-calling - Per-isolate SNP calling for point-mutation panels
- variant-calling/filtering-best-practices - MAF threshold discipline for heteroresistance
- long-read-sequencing/long-read-alignment - Plasmid context resolution
- comparative-genomics/whole-genome-alignment - Reference-based coordinate handling
- workflows/somatic-variant-pipeline - End-to-end orchestration patterns

## Bundled Files

- `epidemiological-genomics--amr-surveillance--examples--amr_surveillance.py` — copied from `examples/amr_surveillance.py`
