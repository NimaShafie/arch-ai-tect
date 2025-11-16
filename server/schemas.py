from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

DiagramType = Literal["c4-context","c4-container","c4-component","deployment","sequence","logical"]
Dialect = Literal["structurizr","plantuml","mermaid"]

class ProjectCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    nav_title: Optional[str] = None

class BriefIn(BaseModel):
    # Mirror your 00_requirements_brief.md schema keys
    # keep names EXACT to avoid drift
    project_name: str
    domain: str
    stakeholders: List[str]
    actors: List[str]
    core_capabilities: List[str]
    key_user_journeys: List[str]
    constraints: List[str]
    non_functional_reqs: List[str]
    tech_preferences: List[str]

class DiagramChoices(BaseModel):
    types: List[DiagramType] = Field(default_factory=lambda: ["c4-context","c4-container","deployment","sequence","logical"])
    dialects: List[Dialect] = Field(default_factory=lambda: ["structurizr","plantuml","mermaid"])

class GenerateRequest(BaseModel):
    refine: bool = True
