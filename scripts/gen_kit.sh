#!/usr/bin/env bash
set -euo pipefail

mkdir -p docs/architecture prompts

cat > mkdocs.yml <<'YAML'
site_name: Architecture Blueprint Kit
theme:
  name: material
  features:
    - navigation.sections
    - content.code.copy
markdown_extensions:
  - admonition
  - toc:
      permalink: true
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.tabbed
nav:
  - Overview: index.md
  - SRS: srs.md
  - Architecture:
    - C4: architecture/c4.md
    - Deployment: architecture/deployment.md
    - Logical: architecture/logical.md
    - Reference Architecture: architecture/reference-architecture.md
  - Implementation Guide: implementation-guide.md
YAML

cat > docs/index.md <<'MD'
# Architecture Blueprint Kit (Agnostic)

Use the prompts to generate C4 (Structurizr), Deployment/Sequence (PlantUML), and Logical (Mermaid)
for any project. Paste outputs into the `diagrams/` files and/or directly into these pages.

- Open WebUI: http://localhost:3000
- Kroki: http://localhost:8000
- PlantUML server: http://localhost:18080
MD

cat > docs/srs.md <<'MD'
# Software Requirements Specification (SRS)

<!-- Replace with output from prompts/40_srs_scaffold.md -->
MD

cat > docs/architecture/c4.md <<'MD'
# C4 Diagrams

```structurizr
// Paste your Structurizr DSL here
```

**Caption (short):** Summarize context/containers, protocols, and auth in 2–4 sentences.
MD

cat > docs/architecture/deployment.md <<'MD'
# Deployment Diagram (PlantUML)

```plantuml
@startuml
' Paste PlantUML deployment here
@enduml
```

**Caption:** 2–3 sentences describing nodes, networks and key protocols.
MD

cat > docs/architecture/logical.md <<'MD'
# Logical Diagram (Mermaid)

```mermaid
%% Paste Mermaid logical diagram here
```

**Caption:** 2–3 sentences describing modules and data flows.
MD

cat > docs/architecture/reference-architecture.md <<'MD'
# Reference Architecture

Explain the architectural decisions supporting the C4/Deployment views, trade-offs, and scaling notes.
MD

cat > docs/implementation-guide.md <<'MD'
# Implementation Guide

<!-- Replace with output from prompts/50_impl_guide.md -->
MD

cat > prompts/00_requirements_brief.md <<'MD'
Return this JSON unchanged to confirm you understand it; do not add commentary.

{
  "project_name": "<<<PROJECT_NAME>>>",
  "domain": "<<<BUSINESS_DOMAIN>>>",
  "stakeholders": ["End User", "Product Manager", "Engineering", "Ops/Sec"],
  "actors": ["Anonymous Visitor", "Authenticated User", "Admin"],
  "core_capabilities": ["<<<CAP1>>>","<<<CAP2>>>","<<<CAP3>>>"],
  "user_journeys": ["<<<JOURNEY1>>>","<<<JOURNEY2>>>"],
  "constraints": ["student-scale","limited budget","privacy-first"],
  "non_functional": {
    "availability": "target 99.5%",
    "latency_p95": "<<<e.g., <300ms page, <2s start>>>",
    "scalability": "modest burst tolerance",
    "security": ["JWT sessions","OWASP ASVS L1"],
    "observability": ["logs","metrics","traces"]
  },
  "tech_preferences": {
    "frontend": "<<<e.g., React static>>>",
    "backend": "<<<e.g., REST over HTTPS>>>",
    "data": "<<<e.g., KV + relational>>>",
    "media_or_streaming": "<<<if applicable>>>",
    "cloud": "<<<agnostic/AWS/GCP/Azure/on-prem>>>"
  }
}
MD

cat > prompts/01_orchestrator.md <<'MD'
You are a senior software architect. Consume the previously confirmed JSON “requirements brief”.
Output ONLY the requested code blocks and captions—no preamble.

TASK:
Generate three diagram artifacts + captions, then two text artifacts:

1) C4 (Context + Container) as Structurizr DSL in one fenced code block labeled `structurizr`.
   - Use names derived from the brief; add protocol/auth labels and tag-based styles.
   - Provide two views: Context and Container.
   - After the code block, add a 2–4 sentence caption.

2) Deployment and Sequence as PlantUML in two separate fenced code blocks, both labeled `plantuml`.
   - Deployment: client/edge/web/api/compute/data/external per the brief.
   - Sequence: pick one key user journey and model end-to-end flow.
   - Add 2–3 sentence captions after each block.

3) Logical diagram as Mermaid in one fenced code block labeled `mermaid`.
   - Show domain modules and data flows grouped by subsystem.
   - Add a short caption.

4) SRS outline (Markdown, no code fence), ~2–4 pages.

5) Implementation Guide (Markdown, no code fence).

CONSTRAINTS:
- Deterministic naming; avoid placeholders.
- Lines ≤ 120 chars.
- Captions short and PM-friendly.
MD

cat > prompts/10_structurizr_refine.md <<'MD'
Refine the Structurizr DSL for consistency and clarity:
- Normalize element names/descriptions
- Ensure protocol/auth labels on relationships
- Apply tag-based styles
Return ONLY one `structurizr` code block + 2–3 sentence caption.

INPUT:
{{PASTE STRUCTURIZR DSL HERE}}
MD

cat > prompts/20_plantuml_refine.md <<'MD'
Improve both PlantUML snippets (Deployment and Sequence):
- Group infra nodes clearly; label protocols (HTTPS/JSON/etc.)
- Sequence lifelines with auth/error notes
Return TWO code blocks labeled `plantuml` (Deployment) and `plantuml` (Sequence) + brief captions.

INPUT:
{{PASTE PLANTUML HERE}}
MD

cat > prompts/30_mermaid_refine.md <<'MD'
Improve the Mermaid logical diagram:
- Group modules by subsystem; label edges; minimize crossings
Return ONE `mermaid` code block + a short caption.

INPUT:
{{PASTE MERMAID HERE}}
MD

cat > prompts/40_srs_scaffold.md <<'MD'
Using the requirements brief and generated diagrams as context, draft a succinct SRS (Markdown):
- Introduction, Stakeholders, Glossary
- Overall Description (user classes, assumptions/constraints)
- Functional Requirements (feature groups)
- External Interfaces (web/api/data/integrations)
- Nonfunctional Requirements (targets, security, privacy)
- Acceptance Criteria (per feature cluster)
Target 2–4 pages. No code fence.
MD

cat > prompts/50_impl_guide.md <<'MD'
Write a concise Implementation Guide (Markdown, no code fence) describing:
- Repo structure and conventions
- Diagram-as-code workflow (Structurizr/PlantUML/Mermaid)
- CI outline (lint docs, render diagrams via Kroki, publish MkDocs)
- Local dev loop with Open WebUI + Ollama prompts
- Packaging to PDF/DOCX with Pandoc
MD

echo "Blueprint Kit files generated."
