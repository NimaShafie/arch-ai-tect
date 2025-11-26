# Services & Endpoints

This section tracks the concrete services that make up the ArchAiTect Workbench stack.

| Service             | URL                                    | Status    | Notes                                       |
|---------------------|----------------------------------------|-----------|---------------------------------------------|
| **Workbench UI**    | `https://workbench.shafie.org/`        | ✅ Online | Project + brief management, runs FastAPI.   |
| **Open WebUI**      | {{ config.extra.endpoints.openwebui }} | ✅ Online | Chat UI backed by Ollama.                   |
| **Kroki**           | {{ config.extra.endpoints.kroki }}     | ✅ Online | HTTP API that renders many diagram formats. |
| **PlantUML Server** | {{ config.extra.endpoints.plantuml }}  | ✅ Online | High-fidelity UML rendering.                |
| **MkDocs (docs)**   | `https://docs.shafie.org/`             | ✅ Online | This documentation site (Material theme).   |

> Tip: when you add or change endpoints (e.g. move Kroki or PlantUML),
> update the values under `extra.endpoints` in `mkdocs.yml` so this table
> and the homepage stay in sync.
