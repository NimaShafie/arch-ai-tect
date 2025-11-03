Goal: Produce an Architecture Package for: {{TITLE}} (slug: {{SLUG}})

Outputs to write plainly (no backticks):
1) spec.md                  — scope, goals, NFRs, assumptions, decisions
2) diagrams/*.puml          — C4 Context/Container/Component/Deployment + Logical (UML)
3) reference-arch.md        — patterns, trade-offs, risks, ADR references
4) implementation-guide.md  — phased steps, DoD/AC per step, roll-back plan
5) jira_issues.json         — epics/stories/tasks with acceptance criteria

Constraints:
- Use C4-PlantUML includes for all C4 diagrams.
- Keep stable IDs and tags for elements; re-usable across updates.
- Outputs must be self-contained and ready for CI to render.
