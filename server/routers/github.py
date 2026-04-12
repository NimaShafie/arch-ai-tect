# server/routers/github.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
import httpx

from server.db import get_session
from server.models import Setting

router = APIRouter(prefix="/api/projects", tags=["github"])

GITHUB_API = "https://api.github.com"


class GitHubConfigIn(BaseModel):
    repo: str   # "owner/repo"
    token: str  # PAT


@router.get("/{slug}/github")
def get_github_config(slug: str, session=Depends(get_session)):
    repo_s = session.exec(
        select(Setting).where(Setting.key == f"project:{slug}:github_repo")
    ).first()
    tok_s = session.exec(
        select(Setting).where(Setting.key == f"project:{slug}:github_token")
    ).first()
    return {
        "repo": repo_s.value if repo_s else None,
        "has_token": tok_s is not None,
    }


@router.post("/{slug}/github")
def save_github_config(slug: str, config: GitHubConfigIn, session=Depends(get_session)):
    if "/" not in config.repo.strip():
        raise HTTPException(
            status_code=400, detail="Repo must be in 'owner/repo' format"
        )
    if not config.token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty")

    for key, val in [
        (f"project:{slug}:github_repo", config.repo.strip()),
        (f"project:{slug}:github_token", config.token.strip()),
    ]:
        s = session.exec(select(Setting).where(Setting.key == key)).first()
        if s:
            s.value = val
        else:
            session.add(Setting(key=key, value=val))
    session.commit()
    return {"ok": True}


@router.post("/{slug}/github/verify")
def verify_github_config(slug: str, session=Depends(get_session)):
    repo_s = session.exec(
        select(Setting).where(Setting.key == f"project:{slug}:github_repo")
    ).first()
    tok_s = session.exec(
        select(Setting).where(Setting.key == f"project:{slug}:github_token")
    ).first()

    if not repo_s or not tok_s:
        raise HTTPException(
            status_code=400, detail="GitHub not configured for this project yet"
        )

    owner_repo = repo_s.value.strip()
    if "/" not in owner_repo:
        raise HTTPException(
            status_code=400, detail="Saved repo is not 'owner/repo' format — please reconfigure"
        )

    owner, repo = owner_repo.split("/", 1)
    headers = {
        "Authorization": f"Bearer {tok_s.value}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        r = httpx.get(
            f"{GITHUB_API}/repos/{owner}/{repo}",
            headers=headers,
            timeout=10,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not reach GitHub: {exc}"
        )

    if r.status_code == 200:
        data = r.json()
        return {
            "ok": True,
            "repo": data.get("full_name"),
            "default_branch": data.get("default_branch"),
            "private": data.get("private", False),
            "html_url": data.get("html_url"),
        }
    if r.status_code == 401:
        raise HTTPException(status_code=400, detail="Token invalid or expired")
    if r.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail="Repo not found — check spelling and that your token has read access",
        )
    raise HTTPException(
        status_code=400, detail=f"GitHub returned status {r.status_code}"
    )
