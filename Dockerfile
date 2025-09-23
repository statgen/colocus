FROM ubuntu:24.04

LABEL org.label-schema.name="colocus"
LABEL org.label-schema.description="Django backend for Colocus browser"
LABEL org.label-schema.vendor="University of Michigan, Center for Statistical Genetics"
LABEL org.label-schema.url="https://github.com/statgen/colocus"
LABEL org.label-schema.usage="https://github.com/statgen/colocus#docker"
LABEL org.label-schema.vcs-url="https://github.com/statgen/colocus"
LABEL org.label-schema.schema-version="1.0"

# Install required packages for LDServer to install.
ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update && apt-get install -y --no-install-recommends \
  git vim curl gnupg lsb-release ca-certificates apt-transport-https \
  nginx sqlite3 libsqlite3-dev python3-virtualenv python3-dev python3-certbot-dns-google \
  build-essential gfortran python3-certbot-nginx locales iputils-ping net-tools postgresql-client \
  && rm -rf /var/lib/apt/lists/* \
  && locale-gen en_US.UTF-8

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8

# Create a group and user to execute as, then drop root
ARG UID
ARG GID
RUN \
  if [ -n "$GID" ]; then \
    addgroup --gid $GID colocus; \
  else \
    addgroup colocus; \
  fi && \
  if [ -n "$UID" ]; then \
    adduser --gecos "User for running colocus as non-root" --shell /bin/bash --disabled-password --uid $UID --ingroup colocus colocus; \
  else \
    adduser --gecos "User for running colocus as non-root" --shell /bin/bash --disabled-password --ingroup colocus colocus; \
  fi

USER colocus

# The application will run from this directory
WORKDIR /opt/colocus

# Data that should persist
VOLUME /data
VOLUME /opt/colocus/database

# Install uv for managing python packages
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/colocus/.local/bin:${PATH}"

# Install python packages before copying source code later on to take advantage of caching
# This way packages are only installed if uv.lock changes
COPY --chown=colocus:colocus pyproject.toml uv.lock /opt/colocus/
RUN \
  uv sync --frozen && \
  chown -R colocus:colocus /opt/colocus/

# Copy the source code into the container
COPY --chown=colocus:colocus . /opt/colocus/

# Run test cases
RUN env DJANGO_SECRET_KEY=1234 DJANGO_SETTINGS_MODULE=config.settings.test \
  bash -c '. .venv/bin/activate && pytest'

# Frequently changing metadata here to avoid cache misses
ARG BUILD_DATE
ARG GIT_SHA
ARG COLOCUS_VERSION

LABEL org.label-schema.version=$COLOCUS_VERSION \
      org.label-schema.vcs-ref=$GIT_SHA \
      org.label-schema.build-date=$BUILD_DATE

# Entry point
ENTRYPOINT ["/opt/colocus/bin/entrypoint-colocus.sh"]
