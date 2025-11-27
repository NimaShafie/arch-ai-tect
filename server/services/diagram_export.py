# server/services/diagram_export.py

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict
import re

from .run_build_nav import encode_plantuml, PLANTUML_SERVER_BASE


@dataclass
class DiagramNode:
    id: str
    label: str
    kind: str  # e.g. "person", "system", "container", "component", "database"


@dataclass
class DiagramEdge:
    source: str
    target: str
    label: str


@dataclass
class DiagramModel:
    type: str         # "c4" or "sequence" or "generic"
    title: str | None
    nodes: List[DiagramNode]
    edges: List[DiagramEdge]


def extract_graph_model_from_plantuml(code: str, title: str | None = None) -> DiagramModel:
    """
    Very small extractor that turns your C4/sequence PlantUML into a neutral
    graph model (nodes + edges). This is a good payload to hand off to another
    AI or an integration layer that talks to Lucidchart/draw.io.
    """
    lines = [ln.strip() for ln in code.splitlines()]
    nodes: Dict[str, DiagramNode] = {}
    edges: List[DiagramEdge] = []
    is_sequence = False

    for ln in lines:
        if not ln or ln.startswith("'"):
            continue
        if ln.lower().startswith("@startuml") or ln.lower().startswith("@enduml"):
            continue
        if ln.startswith("!"):
            continue

        if re.match(r"actor\s+\w+", ln) or re.match(r"participant\s+\w+", ln):
            is_sequence = True

        # C4-style elements
        m = re.match(
            r"(Person|System|Container|Component)\(([^,]+),\s*\"([^\"]+)\"(?:,\s*\"([^\"]+)\")?(?:,\s*\"([^\"]+)\")?",
            ln,
        )
        if m:
            kind, ident, name, tech_or_desc, desc2 = m.groups()
            full_label = name
            if tech_or_desc:
                full_label += f" ({tech_or_desc})"
            if desc2:
                full_label += f" - {desc2}"
            nodes[ident] = DiagramNode(
                id=ident,
                label=full_label,
                kind=kind.lower(),
            )
            continue

        # Relationships
        r = re.match(r"Rel\(([^,]+),\s*([^,]+),\s*\"([^\"]+)\"", ln)
        if r:
            a, b, rel = (p.strip() for p in r.groups())
            edges.append(DiagramEdge(source=a, target=b, label=rel))
            continue

        # Sequence messages
        s = re.match(r"(\w+)\s*[-\.]+>\s*(\w+)\s*:(.+)", ln)
        if s:
            src, dst, msg = s.group(1), s.group(2), s.group(3).strip()
            edges.append(DiagramEdge(source=src, target=dst, label=msg))
            # make sure endpoints exist as generic nodes
            for ident in (src, dst):
                if ident not in nodes:
                    nodes[ident] = DiagramNode(
                        id=ident,
                        label=ident,
                        kind="lifeline",
                    )
            continue

    diag_type = "sequence" if is_sequence else "c4"
    return DiagramModel(
        type=diag_type,
        title=title,
        nodes=list(nodes.values()),
        edges=edges,
    )


def model_to_json(model: DiagramModel) -> dict:
    """
    JSON-ready dict you can send to another service or AI.
    """
    return {
        "type": model.type,
        "title": model.title,
        "nodes": [asdict(n) for n in model.nodes],
        "edges": [asdict(e) for e in model.edges],
    }


def plantuml_viewer_url(code: str) -> str:
    """
    Direct PlantUML viewer URL (you already use this in MkDocs).
    Many tools (e.g., draw.io with the PlantUML plugin) can import from this.
    """
    encoded = encode_plantuml(code)
    return f"{PLANTUML_SERVER_BASE}/uml/{encoded}"


def plantuml_png_url(code: str) -> str:
    """
    Direct PNG URL (useful for tools that just want the rendered image).
    """
    encoded = encode_plantuml(code)
    return f"{PLANTUML_SERVER_BASE}/png/{encoded}"
