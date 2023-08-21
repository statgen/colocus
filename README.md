# colocus [![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)

Visualize and explore colocalization

<!-- TOC -->
  * [Setup](#setup)
    * [Database setup](#database-setup)
    * [Running the django server](#running-the-django-server)
  * [Development](#development)
    * [Running all code checks](#running-all-code-checks)
    * [Running tests](#running-tests)
    * [Live reloading and Sass CSS compilation](#live-reloading-and-sass-css-compilation)
    * [Sentry](#sentry)
  * [Deployment](#deployment)
    * [General deployment](#general-deployment)
    * [CSG](#csg)
  * [Settings](#settings)
  * [Required data](#required-data)
    * [Marginal and conditional analyses](#marginal-and-conditional-analyses)
    * [Linkage disequilibrium (LD)](#linkage-disequilibrium-ld)
    * [Colocalization](#colocalization)
<!-- TOC -->

## Setup

### Database setup

The database can be created by applying relevant migrations, and then loading a pre-packaged dataset (not provided in
this repo, though subsets of data may be provided in the future).

```bash
$ python3 -m venv venv/  # first time, only
$ source venv/bin/activate
$ pip3 install -r requirements/local.txt
$ mkdir database
$ python manage.py migrate
$ python scripts/load_dataset.py <path/to/dataset> # see below for datasets
```

<details>
  <summary><b>Datasets for CSG users</b></summary>

  There is an existing dataset on our cluster at
  `/net/dumbo/home/welchr/projects/amp-cmd/colocus-pipeline-brotman/data/processed/`. The required files are
  approximately 13GB in total. You can quickly sync the required files to your development environment with:

  ```bash
  rsync -avimHP \
    user@dumbo.sph.umich.edu:/home/welchr/projects/amp-cmd/colocus-pipeline-brotman/ \
    /path/on/your/machine/colocus-pipeline-brotman/ \
    --exclude 'data/processed/ld/ukbb_grch37_all/variants' \
    --exclude 'data/original-copy' \
    --exclude 'data/ukbb/' \
    --exclude 'venv' \
    --exclude '.snakemake' \
    --exclude 'logs'
  ```

  Then give the path to the `data/processed` directory as the argument to `load_dataset.py`:

  ```bash
  $ python scripts/load_dataset.py /path/on/your/machine/colocus-pipeline-brotman/data/processed/
  ```
</details>



If you have already tried to load the data previously and want a fresh start, you can delete the database and start over:

```bash
rm -f "./database/local.sqlite3"
rm -rf "./colocus/media"
source venv/bin/activate
python3 manage.py migrate
python3 scripts/load_dataset.py <path/to/dataset>
```

More information on the required types of data can be found below under [required data](#required-data).

### Running the django server

This will start uvicorn to serve the django app and REST API. By default, the server runs on port 8000.

```bash
source venv/bin/activate
uvicorn config.asgi:application --host 0.0.0.0 --reload
```

## Development

### Running all code checks

The project is setup to use [pre-commit](https://pre-commit.com/) to run all checks at once. You can either install
the pre-commit git hooks, or run pre-commit yourself manually before committing.

To run pre-commit manually:

```bash
pre-commit run --all-files -v
```

This is the same command our Github Actions CI will run when you push a commit.

### Running tests

```bash
pytest
```

### Live reloading and Sass CSS compilation

Moved to [Live reloading and SASS compilation](https://cookiecutter-django.readthedocs.io/en/latest/developing-locally.html#sass-compilation-live-reloading).

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account
at <https://sentry.io/signup/?code=cookiecutter> or download and host it yourself.
The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in production.

## Deployment

### General deployment

See detailed [cookiecutter-django documentation](https://cookiecutter-django.readthedocs.io/en/latest/index.html)
for general information on how to deploy either with docker or local install on a server.

### CSG

We have our own deployment and terraform instructions for CSG. There is currently only one site deployed, for an
[adipose eQTL meta-analysis study](https://github.com/statgen/colocus-gcp-adipose).

## Settings

See the [cookie-cutter-django settings documentation](http://cookiecutter-django.readthedocs.io/en/latest/settings.html).

## Required data

### Marginal and conditional analyses

Colocus requires two types of input summary statistics/results. These can come from a GWAS study of one or more
traits, or an eQTL study.

1. The marginal analysis for one or more traits. This is the analysis performed where each variant is tested
   for association with the trait without adjusting for any other variant (only study-specific covariates, if any).
2. Conditional analysis, per locus, per "signal". At each locus, the number of independent signals must be identified,
   either through iterative conditional analysis or a fine-mapping approach
   like [SuSiE](https://stephenslab.github.io/susieR/). Each signal is represented by its lead variant. For each lead
   signal variant, we re-run the association analysis, but adjust for all other lead signal variants in the region by
   including them in the regression model. Software such as [APEX](https://github.com/lin-lab/apex) is capable of doing
   this automatically.

Both analyses end up with roughly the same type of output, though the conditional analysis is done per signal. The
association results are tab-delimited files with the usual columns:

* Variant ID / chrom / pos / reference (ref) allele / alternate (alt) allele
* Association p-value (ideally -log10 p-value)
* Effect size (beta or odds ratio), oriented towards the alternate allele
* Standard error of effect size
* Alternate allele frequency

Layout on disk looks like the following:

```bash
marginal
├── <trait-uuid>
│   ├── metadata.yml
│   ├── signals
│   │   └── <signal-uuid>
│   │       ├── metadata.yml
│   │       ├── results.harmonized.gz
│   │       └── results.harmonized.gz.tbi
│   ├── summ_stats.harmonized.gz
│   └── summ_stats.harmonized.gz.tbi
```

Each trait has its own directory, which should be named with a unique identifier. An example `metadata.yml` file
for a GWAS result contains:

```yaml
uuid: 'T2D_DIAGRAM_2018_hg19'                                   # this must be unique to the trait/study
trait_type: 'gwas'                                              # can be either 'gwas' or 'eQTL'
study_name: 'DIAGRAM'                                           # name of the study
authors: 'DIAGRAM consortium (Mahajan et al. 2018)'             # authors of the study
label: 'T2D Meta-analysis'                                      # label for the analysis
description: 'Latest DIAGRAM T2D meta-analysis as of 2018'      # description of the analysis / where it came from
pmid: '30297969'                                                # PubmedID of the study (if the study is published)
external_link: 'https://diagram-consortium.org/'                # external url for the study if available
genome_build: 'GRCh37'                                          # genome build this study used for positions/alleles
ld_panel: 'ukbb_grch37_all'                                     # the uuid for the LD panel to be used
metadata:
  trait: 'Type 2 Diabetes'                                      # full name of the trait
  trait_abbrev: 'T2D'                                           # an abbreviation for the trait to be used in browser
```

For an eQTL trait, an example `metadata.yml` file looks like:

```yaml
uuid: ENSG00000273398_eqtl_adipose
trait_type: eQTL
study_name: Adipose eQTLs
authors: Authors et al
label: Adipose eQTL meta-analysis
description: Provided by collaborators <link>
pmid: 'pmid if published'
external_link: ''
genome_build: GRCh37
ld_panel: ukbb_grch37_all
metadata:
  gene: RP11-474G23.1                                           # gene symbol
  gene_ensg: ENSG00000273398                                    # ensembl gene id
  tissue: adipose                                               # tissue in which this eQTL study was performed
```

The file `summ_stats.harmonized.gz` contains the marginal association results for the trait. It looks like the
following:

```
#chrom  pos     rsid  ref  alt  neg_log_pvalue  beta    stderr_beta  alt_allele_freq
1       79033   .     A    G    0.509           -0.19   0.19         0.999
<additional rows>
```

The file must be [bgzipped](http://www.htslib.org/doc/bgzip.html) and [tabix](http://www.htslib.org/doc/tabix.html) indexed.

Underneath each trait is a `signals` directory, which contains one subdirectory per signal. Each signal subdirectory
should be named with a unique identifier or uuid. This uuid **must be unique across all signals for all traits**.
The `metadata.yml` file for a signal looks like the following:

```yaml
uuid: '99'
lead_variant_marker: 11_2372356_T_C
lead_variant_chrom: '11'
lead_variant_pos: 2372356
lead_variant_ref: T
lead_variant_alt: C
lead_variant_effect: 0.02942                       # this is the effect size after adjusting for all other signals
lead_variant_effect_marg: 0.029                    # this is the effect size in the marginal analysis
lead_variant_nearest_gene: CD81
lead_variant_nearest_gene_ensg: ENSG00000110651
lead_variant_neg_log_p: 4.05
lead_variant_se: 0.0075
```

In each signal directory is the conditional association results file `results.harmonized.gz` for that signal. It is
identical in format to the `summ_stats.harmonized.gz` file.

### Linkage disequilibrium (LD)

Each lead variant for all signals must have LD calculated between it and all other variants in the region (up to any
distance cutoff, but typically 1 Mb).

Ideally, LD would be calculated either in the original samples used for the GWAS/eQTL study, or in a large reference
panel (one that matches the original population as closely as possible, and ideally the same one that was used when
performing fine-mapping if a reference panel was used in that analysis).

LD information is stored on disk in the following format:

```
ld/
└── <ld-panel-uuid>
    ├── ld.gz
    ├── ld.gz.tbi
    ├── metadata.yml
```

The `ld-panel-uuid` is a unique identifier for the LD panel used to calculate LD. Within each directory, there is a
`metadata.yml` file that provides information about the panel. As an example:

```yaml
uuid: 'ukbb_grch37_all'
panel: 'UKBB'
population: 'ALL'
genome_build: 'GRCh37'
```

The `ld.gz` file contains the calculated LD information, concatenated together and bgzipped. It is a tab-delimited
file with the following format:

```
1       1242707 1:1242707_A/G   1       742813  1:742813_C/T    0.000561357
1       1242707 1:1242707_A/G   1       742825  1:742825_A/G    0.000542286
1       1242707 1:1242707_A/G   1       742832  1:742832_C/A    0.000123633
```

Columns 1, 2, 3 pertain to the lead variant. They are the chromosome, position, and variant ID respectively.

Columns 4, 5, 6 pertain to the "other" variants in the region. They are also the chromosome, position, and variant ID.

The final column is the LD (r2) value between the lead variant and the other variant.

This file should be sorted by chromosome and position for the lead variants (columns 1-3), and then bgzipped and
tabix indexed.

### Colocalization

Colocalization results are stored on disk in the following format:

```
coloc/
├── <coloc-uuid>
    └── metadata.yml
```

Each colocalization result for a pair of signals is stored in a separate directory and given its own unique uuid.
These ids must be unique across all colocalization results for all traits.

The `metadata.yml` file has the following information:

```yaml
uuid: 4293814906                          # unique identifier for this colocalization result

signal1: 3258419243                       # uuid of the first signal
signal2: 3508799139                       # uuid of the second signal

study1: 2hGlu_MAGIC_2021_hg19             # first signal's study uuid
study2: brotman_eqtl                      # second signal's study uuid

trait1_variant: 2_27730940_T_C            # lead variant for the first signal
trait2_variant: 2_27734972_G_A            # lead variant for the second signal

coloc_h3: 0.25
coloc_h4: 0.75                            # posterior probability of colocalization

cross_signal:                             # cross signal information; each subfield 'effect', 'se', etc.
  effect:                                 # is a list of lists (a matrix), where:
  - - -0.0486                             #   row 1 is the first trait's variant,
    - -0.0594                             #   row 2 is the second trait's variant,
  - - -0.0338                             #   col 1 is the first trait's data (effect in marginal summary statistics)
    - -0.0636                             #   col 2 is the second trait's data (effect in marginal summary statistics)
  log_pval:
  - - 11.2
    - 6.44
  - - 5.93
    - 7.54
  se:
  - - 0.0078
    - 0.0116
  - - 0.0077
    - 0.0114

n_coloc_between_traits: 1                 # number of total colocalizations found between the two traits; this is used
                                          # in the web UI

qtl_gene: ENSG00000163795                 # if trait 2 comes from an eQTL study, this is the gene's ENSG ID
qtl_symb: ZNF513                          # if trait 2 comes from an eQTL study, this is the gene's symbol

r2: 0.778088                              # this is the LD between the two lead variants
```
