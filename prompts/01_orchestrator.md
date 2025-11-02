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
