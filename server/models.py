from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    nav_title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    artifacts: List["Artifact"] = Relationship(back_populates="project")

class Artifact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    kind: str
    path: str
    sha256: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    project: Project = Relationship(back_populates="artifacts")

class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
