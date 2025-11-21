# server/db.py
from __future__ import annotations

import os, pathlib, sqlite3
from typing import Optional

from sqlmodel import SQLModel, create_engine, Session

# Put the DB in a writable folder (./data). Allow override by env.
DEFAULT_DB = os.path.join("data", "aw.sqlite")
DB_PATH = os.environ.get("AW_DB_PATH", DEFAULT_DB)

# Ensure parent directory exists
pathlib.Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

def get_session() -> Session:
    return Session(engine)

def _sqlite_has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    for _cid, name, _type, _notnull, _dflt, _pk in cur.fetchall():
        if name == col:
            return True
    return False

def _migrate_v1_add_user_id():
    """
    Add nullable 'user_id' column to 'project' if missing (backward compatibility).
    """
    raw = sqlite3.connect(DB_PATH)
    try:
        if not _sqlite_has_column(raw, "project", "user_id"):
            raw.execute('ALTER TABLE "project" ADD COLUMN "user_id" INTEGER NULL;')
            raw.commit()
    finally:
        raw.close()

def init_db():
    # Import models to register tables
    from .models import Project, Artifact, Setting, User  # noqa
    SQLModel.metadata.create_all(engine)

    # Lightweight, idempotent migrations for SQLite
    _migrate_v1_add_user_id()
