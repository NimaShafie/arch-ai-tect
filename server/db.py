# server/db.py
from sqlmodel import SQLModel, create_engine, Session
import os, pathlib

# Put the DB in a writable folder (./data). Allow override by env.
DEFAULT_DB = os.path.join("data", "aw.sqlite")
DB_PATH = os.environ.get("AW_DB_PATH", DEFAULT_DB)

# Ensure parent directory exists
pathlib.Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

def init_db():
    from .models import Project, Artifact, Setting
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
