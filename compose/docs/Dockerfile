# compose/docs/Dockerfile
FROM squidfunk/mkdocs-material:latest

# Add plugins you use in mkdocs.yml
RUN pip install --no-cache-dir \
    mkdocs-macros-plugin \
    mkdocs-kroki-plugin \
    pymdown-extensions

WORKDIR /work
# (No ENTRYPOINT/CMD here; compose supplies the command)
