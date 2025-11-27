# compose/docs/Dockerfile

FROM python:3.12-slim

# System deps for building Python packages & using git/curl
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Everything in the container will live under /work
WORKDIR /work

# Copy the requirements files needed for install
# Build context is repo root (.. in docker-compose.yml)
COPY requirements.txt ./requirements.txt
COPY server/requirements.txt ./server/requirements.txt
COPY docs/requirements.txt ./docs/requirements.txt
COPY site/requirements.txt ./site/requirements.txt

# Install your project deps (this brings in sqlmodel etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Install MkDocs + plugins
RUN pip install --no-cache-dir \
      mkdocs \
      mkdocs-material \
      mkdocs-material-extensions \
      mkdocs-macros-plugin \
      mkdocs-exclude \
      mkdocs-monorepo-plugin \
      mkdocs-awesome-pages-plugin

# MkDocs cache
ENV XDG_CACHE_HOME=/var/mkdocs/cache
