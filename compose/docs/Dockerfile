FROM python:3.12-slim

# Install system dependencies (needed for mkdocs & plugins)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       build-essential \
       git \
       curl \
       ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install MkDocs + Material + plugins
RUN pip install --no-cache-dir \
      mkdocs \
      mkdocs-material \
      mkdocs-material-extensions \
      mkdocs-macros-plugin \
      mkdocs-exclude \
      mkdocs-kroki-plugin

# Make the working dir inside the container
WORKDIR /work

EXPOSE 8080

CMD [ "mkdocs", "serve", "-a", "0.0.0.0:8080" ]
