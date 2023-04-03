# colocus [![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)

Visualize and explore colocalization

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
