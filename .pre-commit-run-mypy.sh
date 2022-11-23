#!/bin/bash
set -o errexit

# Same dependencies used for project must also be installed in the virtualenv that
# precommit creates for running mypy (so that mypy can find type information on dependencies).
# First time run is slow, much faster afterwards.
pip install --no-input --quiet -r requirements/base.txt
pip install --no-input --quiet -r requirements/local.txt

# Run mypy using config
mypy --config-file setup.cfg ./colocus/
