#!/bin/bash
set -euxo pipefail

COLOCUS_VERSION=`git describe --tags --abbrev=11 | sed 's/^v//' | sed 's/-g/-/'`
GIT_SHA=`git rev-parse HEAD`
BUILD_DATE=`date -u +'%Y-%m-%dT%H:%M:%SZ'`

docker build --pull -t colocus:${COLOCUS_VERSION} \
  --build-arg MAKEFLAGS="-j 3" \
  --build-arg CMAKE_BUILD_PARALLEL_LEVEL=3 \
  --build-arg BUILD_DATE=${BUILD_DATE} \
  --build-arg GIT_SHA=${GIT_SHA} \
  --build-arg COLOCUS_VERSION=${COLOCUS_VERSION} \
  --progress plain \
  "$@" .

docker tag colocus:${COLOCUS_VERSION} colocus:latest
