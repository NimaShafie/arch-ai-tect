# Architecture Blueprint Kit (Agnostic)

Use these prompts and tools to generate C4 (Structurizr), Deployment/Sequence (PlantUML), and Logical (Mermaid) diagrams for any project. Paste outputs into the `diagrams/` folder or directly into these pages.

---

## Live endpoints

- **Open WebUI (Ollama backend):** https://ai.shafie.org/
- **Kroki (diagram as a service):** _not deployed_ (placeholder was `http://localhost:8000`)
- **PlantUML server:** _not deployed_ (placeholder was `http://localhost:18080`)

> ℹ️ When Kroki or PlantUML go live, update the URLs here and on the **Services** page.

---

## What we’re building

- **Self-hosted AI workbench** for architecture docs & diagrams  
  - Chat + prompt workflows via **Open WebUI** backed by **Ollama**
  - MkDocs Material site as the canonical, linkable knowledge base  
- **Diagramming**:
  - Mermaid (inline in Markdown)
  - _(Planned)_ Kroki for many formats (Mermaid/PlantUML/Graphviz/etc.)
  - _(Planned)_ Dedicated PlantUML server for higher-fidelity UML

---

## Stack at a glance

- **Docs**: MkDocs + Material theme
- **AI**: Open WebUI ↔ Ollama (models cached in Docker volume)
- **Reverse proxy / TLS**: Nginx + Let’s Encrypt (ai.shafie.org, docs.shafie.org)
- **Infra**: Docker Compose

---

See the [Catalog](catalog.md) for all architecture packages.

---

## Next steps (roadmap)

- [ ] Stand up **Kroki** behind your proxy (e.g., `https://kroki.shafie.org/`)
- [ ] Stand up **PlantUML** (e.g., `https://uml.shafie.org/`)
- [ ] Add example C4, sequence, and deployment diagrams under `diagrams/`
- [ ] Document backup/restore for model cache and docs build artifacts
