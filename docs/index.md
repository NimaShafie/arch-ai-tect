# ArchAiTect Workbench Docs

This site is the documentation front-end for the **ArchAiTect Workbench**.

The flow looks like this:

1. You create or update a project in the Workbench UI at `https://workbench.shafie.org/`.
2. The Workbench writes package docs and diagram stubs into the `docs/` tree under `/projects/<slug>/`.
3. MkDocs Material builds those files and serves them here at `https://docs.shafie.org/`.

Use the **Projects** section in the left navigation to jump straight into a project workspace.

---

## Live endpoints

- **Workbench UI:** `https://workbench.shafie.org/`
- **Open WebUI (chat frontend):** {{ config.extra.endpoints.openwebui }}
- **Kroki (diagram as a service):** {{ config.extra.endpoints.kroki }}
- **PlantUML server:** {{ config.extra.endpoints.plantuml }}
- **MkDocs (this site):** `https://docs.shafie.org/`

All of these run inside the same self-hosted stack and are wired together by the Workbench backend.

---

## What we're building

- **Self-hosted AI workbench** for architecture docs & diagrams  
  - Projects and briefs are managed via the FastAPI Workbench (`workbench.shafie.org`).
  - Diagrams and specs are generated into this MkDocs site.
- **Diagramming:**
  - Mermaid (inline in Markdown).
  - Kroki + PlantUML for richer sequence/deployment/UML diagrams.
- **Canonical knowledge base:**
  - Each project lives under `/projects/<slug>/` with:
    - Package docs (Spec, SRS, Reference Architecture, Implementation Guide).
    - A `diagrams/` area for C4 / sequence / deployment diagrams.

---

## Stack at a glance

- **Docs:** MkDocs + Material theme (this site)
- **AI & prompts:** Open WebUI ↔ Ollama (LLM backend)
- **Workbench API:** FastAPI app that owns projects, briefs, and generators
- **Diagram rendering:** Kroki + PlantUML containers
- **Reverse proxy / TLS:** Cloudflared tunnel + Nginx / TLS endpoints
- **Infra:** Docker Compose

---

## Next steps

- Create a project in the Workbench and save a brief.
- Run the generators so package docs & diagram stubs are written under `/docs/projects/<slug>/`.
- Commit & deploy the updated docs so they appear automatically under **Projects** in this site.
