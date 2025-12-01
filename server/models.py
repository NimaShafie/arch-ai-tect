from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    display_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    projects: List["Project"] = Relationship(back_populates="owner")


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    name: str
    nav_title: str
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")  # None => legacy/unassigned
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    owner: Optional[User] = Relationship(back_populates="projects")
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
