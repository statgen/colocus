# colocus

Visualize and explore fine-mapped signals and their colocalizations

To see an example of a running instance of Colocus, try: https://amp.colocus.app/.

<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->

This repository contains the code for the backend server component of Colocus, as well as a docker compose stack to help
deploy it.

## Deployment

### Docker

A `.env` file must be created before starting the services via docker compose. There are examples in the `envs/` directory for a local deployment (`env.local`), and for a production one (`env.production`). Copy one, modify it, and save it to the root of the directory as `.env`. You will only need to change a few values, such as the postgres password and django secret key.

Inside the `.env` file, be sure to set your `DATA_PATH`, which points to the location on disk where your data is located. This path must have permissions set such that the container is able to read it. You will need to either make all files world readable, or set them to a group of ID 1001 with read permissions (and execute on directories). Alternatively you could use ACL permissions as well. For example:

```bash
# Make world readable
chmod o+rX -R /path/to/data

# Alternatively, make all files GID 1001
chgrp -R 1001 /path/to/data
chmod g+rX -R /path/to/data
```

Now you can start the docker compose stack:

```bash
# This will build images and enable docker compose watch (see docker-compose.override.yml instructions below.)
docker compose up -d --build --watch
```

When the `colocus-django` container starts, it will begin applying django migrations and then load the data located at the `DATA_PATH` specified in your `.env` file.

In the future, if you wish to start over and load a new dataset, do the following:

```bash
# If loading data from a new path:
# Change your `DATA_PATH` in your `.env` file to match the location of your dataset
# Then restart to force docker to remount DATA_PATH inside the container
# It's best to recreate the container and build so that your new migrations are included (if any)
docker compose up -d --build --force-recreate django

# If you're just reloading an existing dataset in the same DATA_PATH as before, you can start here:
docker compose exec db bash -c 'psql -U colocus -c "DROP DATABASE core WITH (FORCE)"'
docker compose exec db bash /docker-entrypoint-initdb.d/init-db.sh
docker compose exec django bash -c 'source .venv/bin/activate && python3 manage.py migrate --database=core'
docker compose exec django bash -c 'source .venv/bin/activate && python3 scripts/load_dataset.py /data'
```

For debugging a new dataset load:

```bash
# Get a shell in container
docker compose exec django bash

# From inside container
source .venv/bin/activate
python3 -m pdb scripts/load_dataset.py /data
```

While developing you may want the containers to rebuild or resync with your source files changing automatically. The following can be placed in a `docker-compose.override.yml` file: 

```yml
services:
  django:
    build: .
    command: --reload
    develop:
      watch:
        - action: sync
          path: ./colocus
          target: /opt/colocus/colocus
        - action: sync
          path: ./colocus/core/migrations
          target: /opt/colocus/colocus/core/migrations
        - action: sync
          path: ./scripts
          target: /opt/colocus/scripts
        - action: rebuild
          path: ./Dockerfile

  ui:
    build:
      context: ../colocus-ui-vue3
      dockerfile: Dockerfile.dev
    ports:
      - "${VITE_PORT}:${VITE_PORT}"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${VITE_PORT}"]
      interval: 5s
      timeout: 5s
      retries: 5
    develop:
      watch:
        - action: rebuild
          path: ../colocus-ui-vue3/package.json
        - action: rebuild
          path: ../colocus-ui-vue3/vite.config.mjs
        - action: sync
          path: ../colocus-ui-vue3/src
          target: /app/src
        - action: sync
          path: ../colocus-ui-vue3/etc
          target: /app/etc
        - action: rebuild
          path: ../colocus-ui-vue3/Dockerfile.dev
```

This assumes you have `colocus` and `colocus-ui-vue3` repositories checked out and next to each other in the directory hierarchy. 

You'll also want the following in your `.env` file: 

```bash
VITE_HOST=0.0.0.0
VITE_PORT=5173
VITE_API_URL=http://django:${UVICORN_PORT}
```


### CSG

We have our own deployment and terraform instructions for CSG. There is currently one site deployed, for the
[Accelerating Medicines Parternship (AMP) group](https://github.com/statgen/colocus-gcp-amp).

## Required data

Colocus requires a fair number of pieces of data together to function. You will need:

* Marginal association analysis (GWAS, eQTLs)
* Fine-mapping or conditional analysis at loci of interest in your GWAS or eQTL study
* Colocalization analysis results for the signals identified from fine-mapping
* LD that was used to perform the fine-mapping (this is only used for coloring LD on LocusZoom plots and need not be perfect, but ideally will be as close as possible to the fine-mapping LD.)

### Marginal and conditional / fine-mapping analyses

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

Directory structure on disk looks like the following:

```
marginal
├── <dataset UUID>
│  ├── metadata.parquet
│  ├── <trait UUID>
│  │  ├── metadata.parquet
│  │  ├── signals
│  │  │  └── <signal UUID>
│  │  │     ├── metadata.parquet
│  │  │     ├── results.harmonized.gz
│  │  │     └── results.harmonized.gz.tbi
│  │  ├── summ_stats.harmonized.gz
│  │  └── summ_stats.harmonized.gz.tbi
signals.parquet
coloc
└── coloc.parquet
ld
└── UKBB_GRCh37_ALL
   ├── ld.gz
   ├── ld.gz.tbi
   └── metadata.yml
```

Each trait has its own directory, which should be named with a unique identifier (UUID). An example `metadata.parquet` file for a GWAS result contains:

```json
{
  "uuid": "gwas_diamante_t2d_eur",
  "study": {
    "uuid": "DIAMANTE",
    "description": "Diabetes Meta-Analysis of Trans-Ethnic Association Studies"
  },
  "tissue": null,
  "ancestry": "EUR",
  "publication": {
    "authors": "Mahajan et al.",
    "journal": "Nature Genetics",
    "year": 2022,
    "pmid": 35551307,
    "doi": null
  },
  "analysts": null,
  "submitter": {
    "name": "<last name, first name>",
    "abbrev": "<abbrev>",
    "email": "<email>",
    "orcid": "<orcid>",
    "institution": "University of Michigan"
  },
  "principal_investigators": null,
  "genome_build": "GRCh37",
  "ld": "UKBB_GRCh37_ALL",
  "external_link": "https://diagram-consortium.org/downloads.html",
  "analysis_type": "GWAS",
  "n_traits": 1,
  "n_traits_with_sig": 1
}
```

The parquet file above was rendered in JSON format to make it easier to read, but note that parquet is a columnar data
frame format. The metadata file has only a single row above.

For an eQTL trait, an example `metadata.parquet` file looks like:

```json
{
  "uuid": "eqtl_inspire_islet",
  "study": {
    "uuid": "INSPIRE",
    "description": "INSPIRE islet eQTL meta-analysis consortium"
  },
  "tissue": "islet",
  "ancestry": "EUR",
  "publication": {
    "authors": "Viñuela et al.",
    "pmid": 32999275,
    "journal": "Nature Communications",
    "year": 2020,
    "doi": null
  },
  "analysts": [
    {
      "name": "<last name, first name>",
      "abbrev": "<initials>",
      "email": "<email>",
      "orcid": "<orcid>",
      "institution": "University of Michigan"
    }
  ],
  "submitter": {
    "name": "<last name, first name>",
    "abbrev": "<initials>",
    "email": "<email>",
    "orcid": "<orcid>",
    "institution": "University of Michigan"
  },
  "principal_investigators": null,
  "genome_build": "GRCh37",
  "ld": "UKBB_GRCh37_ALL",
  "external_link": null,
  "analysis_type": "eQTL",
  "n_traits": 236,
  "n_traits_with_sig": 236
}
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
The `metadata.parquet` file for a signal looks like the following:

```json
{
  "uuid": "Lc7hEWyp24Nco8j97GXrfr",
  "lead_variant": {
    "chrom": "9",
    "pos": 136241189,
    "ref": "C",
    "alt": "T"
  },
  "neg_log_p": 51.647,
  "effect_cond": -15.196,
  "se_cond": 0.998,
  "effect_marg": -0.307,
  "is_marg": false,
  "cs_variants": [
    "9_136218590_C_A",
    "9_136238509_G_A",
    "9_136241189_C_T",
    "9_136241639_C_T",
    "9_136249929_G_A",
    "9_136264493_C_T",
    "9_136267371_G_T"
  ],
  "cs_alpha": [
    0.0665931,
    0.037789,
    0.4947666,
    0.0755713,
    0.1302856,
    0.1038847,
    0.0618499
  ],
  "finemap_program": {
    "name": "susieR",
    "version": "v0.0.0"
  }
}
```

The fields above are mostly self explanatory. Some require a bit of clarification:

* `neg_log_p`: This is the p-value from conditional analysis or fine-mapping

* `effect_cond` and `effect_marg`: The effect size from the conditional analysis or fine-mapping, and the marginal effect size.

* `is_marg`: This denotes whether this particular signal was taken from the marginal association statistics directly. Sometimes it is the case that no fine-mapping is done at a particular locus, for example in the event there is only a single association signal, or if fine-mapping fails.

* `cs_alpha`: This field is only present if the fine-mapping was done with SuSiE. In that case, the alphas are the posterior inclusion probabilities (conditional on the signal) for each credible set variant. The marginal inclusion probabilities can be found in the `results.harmonized.gz` file.

* `cs_variants`: This field contains the list of each variant in the credible set. The values in `cs_alpha` correspond in order to each variant in this list.

In each signal directory is the conditional association results file `results.harmonized.gz` for that signal. It is
identical in format to the `summ_stats.harmonized.gz` file.

There is also a master `signals.parquet` file that contains the information about all signals across all datasets. This file is *NOT REQUIRED*, however it may be useful for debugging. Each record in the file looks like the following (rendered as JSON for easier reading):

```json
{
  "sig_uuid": "UXPTfTuQtfikGyjD2hHKmh",
  "study_uuid": "gwas_diamante_t2d_eur",
  "lead_variant": "4_1784403_C_T",
  "susie_idx": 1,
  "susie_cs": 1,
  "susie_cs_variants": [
    "4_1784403_C_T",
    "4_1784605_G_C"
  ],
  "susie_cs_alpha": [
    0.7572763,
    0.1992575
  ],
  "path": "data/orig/muscislet/t2d_gwas_susie/diamante_T2D-European__MAEA__rs56337234__P__chr4-1534402-2034403__250kb.selected.Rda",
  "extract_marginal": false,
  "study_type": "GWAS",
  "trait": "T2D",
  "gene": null,
  "exon": null,
  "feature": "T2D",
  "tissue": null,
  "cell_type": null,
  "trust_alleles": true,
  "finemap_program": "susieR",
  "finemap_version": "v0.0.0",
  "genome_build": "GRCh37"
}
```

Fields that require some explanation:

* `susie_idx`: If this record is for a fine-mapped signal that came from SuSiE, this field will contain the row index of the SuSiE matrices (such as alpha, mu, mu2, lbf_variable, etc.) to extract.
* `susie_cs`: This is index into the SuSiE credible sets list
* `extract_marginal`: Same as `extract_marg` in the individual metadata files for each signal. Denotes whether this signal was extracted from the marginal association data, perhaps because fine-mapping was not run or failed.
* `trust_alleles`: Setting denotes whether we can trust the alleles provided by the study. If we cannot trust the alleles, they have been remapped using dbSNP and/or the LD reference to identify which variant is the ref and which is the alt.

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
uuid: 'UKBB_GRCh37_ALL'
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

Colocalization results are stored on disk in a single file:

```
coloc
└── coloc.parquet
```

Each colocalization result for a pair of signals is given its own unique UUID. These UUIDs must be unique across all colocalization results for all traits.

The `metadata.parquet` file has the following information:

```json
{
  "uuid": "7yCjsigpyW9AWVgcqM7SkF",
  "signal1": "918mCCrkd6US8F8qbyLDoi",
  "signal2": "EuaY2JFmhPH7fAUEduozHz",
  "coloc_h3": 0.904439412729006,
  "coloc_h4": 0.0034383473563195,
  "dataset1": "gwas_diamante_t2d_eur",
  "dataset2": "eqtl_inspire_islet",
  "trait1": "T2D",
  "trait2": "ENSG00000114770_183645118_183645231",
  "trait2_symb": null,
  "trait1_variant": "3_183738626_T_A",
  "trait2_variant": "3_183683124_G_A",
  "cross_signal": {
    "effect": [
      [
        -0.036,
        0.0468
      ],
      [
        -0.018,
        0.35
      ]
    ],
    "se": [
      [
        0.0063,
        0.0322
      ],
      [
        0.013,
        0.0667
      ]
    ],
    "log_pval": [
      [
        7.7,
        0.835
      ],
      [
        0.796,
        6.59
      ]
    ]
  },
  "r2": 0.0564906,
  "n_coloc_between_traits": 0
}
```

The fields are:

* uuid: unique identifier for this colocalization result
* signal1: uuid of the first signal
* signal2: uuid of the second signal
* dataset1: first signal's study uuid
* dataset2: second signal's study uuid
* trait1: uuid of the first trait
* trait2: uuid of the second trait
* trait2_symb: gene symbol of trait 2 if applicable
* trait1_variant: lead variant for the first signal
* trait2_variant: lead variant for the second signal
* coloc_h3: Posterior probability of H3 from coloc
* coloc_h4: Posterior probability of H4 from coloc
* cross_signal: cross signal information; each subfield 'effect', 'se', etc. is a list of lists (a matrix), where:
  * row 1 is the first trait's variant,
  * row 2 is the second trait's variant,
  * col 1 is the first trait's data (effect in marginal summary statistics)
  * col 2 is the second trait's data (effect in marginal summary statistics)
* n_coloc_between_traits: number of total colocalizations found between the two traits; this is used in the web UI
* r2: the LD between trait1_variant and trait2_variant

## Development

### Bare metal

This development setup deploys the colocus server directly to your VM or local machine. For a docker based setup, see below.

#### Database setup

We use `uv` to manage packages and dependencies. [Follow these instructions](https://docs.astral.sh/uv/getting-started/installation/) to install `uv` on your system.

The database can be created by applying relevant migrations, and then loading a pre-packaged dataset (not provided in
this repo, though subsets of data may be provided in the future).

```bash
$ cd /path/to/colocus
$ uv sync
$ mkdir database
$ uv run python manage.py migrate
$ uv run python scripts/load_dataset.py <path/to/dataset> # see below for datasets
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
  $ uv run python scripts/load_dataset.py /path/on/your/machine/colocus-pipeline-brotman/data/processed/
  ```
</details>



If you have already tried to load the data previously and want a fresh start, you can delete the database and start over:

```bash
rm -f "./database/local.sqlite3"
rm -rf "./colocus/media"
uv run python manage.py migrate
uv run python scripts/load_dataset.py <path/to/dataset>
```

More information on the required types of data can be found below under [required data](#required-data).

#### Running the django server

This will start uvicorn to serve the django app and REST API. By default, the server runs on port 8000.

```bash
uv run uvicorn config.asgi:application --host 0.0.0.0 --reload
```

#### Running all code checks

The project is setup to use [pre-commit](https://pre-commit.com/) to run all checks at once. You can either install
the pre-commit git hooks, or run pre-commit yourself manually before committing.

To run pre-commit manually:

```bash
uv run pre-commit run --all-files -v
```

This is the same command our Github Actions CI will run when you push a commit.

#### Running tests

```bash
uv run pytest
```

#### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/> or download and host it yourself. The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in `SENTRY_DSN` in your `.env` file.

### Docker

Make a docker compose override that enables watching files and rebuilding container images as needed:

```yml
services:
  django:
    build: .
    command: --reload
    develop:
      watch:
        - action: sync
          path: ./colocus
          target: /opt/colocus/colocus

  ui:
    build:
      context: ../colocus-ui-vue3
      dockerfile: Dockerfile
    develop:
      watch:
        - action: rebuild
          path: ../colocus-ui-vue3/package.json
        - action: rebuild
          path: ../colocus-ui-vue3/src
```

To use this, you will need the `colocus-ui-vue3` repository checked out next to colocus. For example, your directory tree should look like this:

```
root
| - colocus-ui-vue3
| - colocus
```

Now you can run:

```bash
docker compose up --build --watch
```

This will bring up the containers, building them as needed, and watch to see if source code files change. If any of the source changes, the container image will be rebuilt if necessary, and restarted. In the case of the Django container, it will instead just sync the new source files into the container, and then the uvicorn server will reload them.
