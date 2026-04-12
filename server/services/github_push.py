# server/services/github_push.py
from __future__ import annotations

import base64
from typing import Dict

import httpx

GITHUB_API = "https://api.github.com"


class GitHubPushError(Exception):
    pass


def push_files_to_github(
    owner: str,
    repo: str,
    token: str,
    files: Dict[str, str],
    message: str,
) -> dict:
    """
    Push multiple files to GitHub in a single commit via the Git Trees API.

    Args:
        owner:   GitHub username or org
        repo:    Repository name
        token:   Fine-grained or classic PAT with Contents: Read & Write
        files:   {path_from_repo_root: content_string}
        message: Commit message

    Returns dict with commit_sha, commit_sha_short, commit_url,
    files_pushed, branch, repo_url, repo_tree_url.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        with httpx.Client(headers=headers, timeout=30) as client:
            # 1) Repo metadata — determine default branch
            r = client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
            if r.status_code == 401:
                raise GitHubPushError("Invalid token — check your PAT and its expiry")
            if r.status_code == 404:
                raise GitHubPushError(
                    f"Repo '{owner}/{repo}' not found or token lacks read access"
                )
            r.raise_for_status()
            branch = r.json().get("default_branch", "main")

            # 2) Current HEAD commit + tree on that branch
            r = client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
            )
            r.raise_for_status()
            parent_commit_sha: str = r.json()["object"]["sha"]

            r = client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/commits/{parent_commit_sha}"
            )
            r.raise_for_status()
            base_tree_sha: str = r.json()["tree"]["sha"]

            # 3) Create a blob for every file
            tree_items = []
            for path, content in files.items():
                r = client.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs",
                    json={
                        "content": base64.b64encode(
                            content.encode("utf-8")
                        ).decode("ascii"),
                        "encoding": "base64",
                    },
                )
                r.raise_for_status()
                tree_items.append(
                    {
                        "path": path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": r.json()["sha"],
                    }
                )

            # 4) Create new tree on top of the existing one
            r = client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees",
                json={"base_tree": base_tree_sha, "tree": tree_items},
            )
            r.raise_for_status()
            new_tree_sha: str = r.json()["sha"]

            # 5) Create the commit
            r = client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/commits",
                json={
                    "message": message,
                    "tree": new_tree_sha,
                    "parents": [parent_commit_sha],
                },
            )
            r.raise_for_status()
            commit_sha: str = r.json()["sha"]

            # 6) Advance the branch ref (fast-forward; force if diverged)
            r = client.patch(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{branch}",
                json={"sha": commit_sha, "force": False},
            )
            if r.status_code == 422:
                r = client.patch(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{branch}",
                    json={"sha": commit_sha, "force": True},
                )
            r.raise_for_status()

    except GitHubPushError:
        raise
    except httpx.HTTPStatusError as exc:
        raise GitHubPushError(
            f"GitHub API error ({exc.response.status_code}): "
            f"{exc.response.text[:300]}"
        ) from exc
    except httpx.RequestError as exc:
        raise GitHubPushError(f"Network error reaching GitHub: {exc}") from exc

    return {
        "commit_sha": commit_sha,
        "commit_sha_short": commit_sha[:7],
        "commit_url": f"https://github.com/{owner}/{repo}/commit/{commit_sha}",
        "files_pushed": list(files.keys()),
        "branch": branch,
        "repo_url": f"https://github.com/{owner}/{repo}",
        "repo_tree_url": f"https://github.com/{owner}/{repo}/tree/{branch}",
    }
