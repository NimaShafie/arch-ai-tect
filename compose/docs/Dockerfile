# compose/docs/Dockerfile
FROM squidfunk/mkdocs-material:latest

# Install plugins referenced by mkdocs.yml
RUN pip install --no-cache-dir \
    mkdocs-exclude \
    mkdocs-macros-plugin \
    mkdocs-redirects \
    mkdocs-git-revision-date-localized-plugin \
    mkdocs-kroki-plugin \
    pymdown-extensions

WORKDIR /work
