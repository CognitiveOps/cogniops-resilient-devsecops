"""GitHub API client for execution tools.

Provides workflow_dispatch and issue creation for:
  - ROLLBACK → dispatch s3 rollback workflow
  - BLOCK → dispatch block notification
  - ESCALATE → create HITL issue

Auth via ``GITHUB_TOKEN`` env var (PAT or GitHub App installation token,
fetched at runtime from Secret Manager or injected by Cloud Run).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("runtime-agent.github")

GITHUB_API = "https://api.github.com"
GITHUB_TIMEOUT_SEC = float(os.getenv("GITHUB_TIMEOUT_SEC", "10"))


def _repo_slug() -> str:
    """Return owner/repo from env, e.g. ``myorg/cogniops-resilient-devsecops``."""
    return os.getenv("GITHUB_REPOSITORY", "")


def _token() -> str | None:
    return os.getenv("GITHUB_TOKEN")


@dataclass
class GitHubResult:
    """Outcome of a GitHub API call."""

    ok: bool
    status_code: int = 0
    url: str = ""
    error: str | None = None


async def dispatch_workflow(
    workflow_file: str,
    ref: str = "main",
    inputs: dict | None = None,
) -> GitHubResult:
    """Trigger a GitHub Actions workflow via workflow_dispatch.

    POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
    """
    import httpx

    repo = _repo_slug()
    token = _token()

    if not repo:
        return GitHubResult(ok=False, error="GITHUB_REPOSITORY not set")
    if not token:
        return GitHubResult(ok=False, error="GITHUB_TOKEN not set")

    url = f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    payload: dict = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT_SEC) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code in (204, 200):
            logger.info("Dispatched workflow %s (ref=%s)", workflow_file, ref)
            return GitHubResult(ok=True, status_code=resp.status_code, url=url)

        msg = f"GitHub dispatch failed: HTTP {resp.status_code} — {resp.text[:200]}"
        logger.error(msg)
        return GitHubResult(ok=False, status_code=resp.status_code, url=url, error=msg)

    except Exception as exc:
        msg = f"GitHub API unreachable: {exc}"
        logger.error(msg)
        return GitHubResult(ok=False, error=msg)


async def create_issue(
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> GitHubResult:
    """Create a GitHub issue (for ESCALATE / advisory notifications).

    POST /repos/{owner}/{repo}/issues
    """
    import httpx

    repo = _repo_slug()
    token = _token()

    if not repo:
        return GitHubResult(ok=False, error="GITHUB_REPOSITORY not set")
    if not token:
        return GitHubResult(ok=False, error="GITHUB_TOKEN not set")

    url = f"{GITHUB_API}/repos/{repo}/issues"
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT_SEC) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code in (201, 200):
            issue_url = resp.json().get("html_url", "")
            logger.info("Created issue: %s", issue_url)
            return GitHubResult(
                ok=True,
                status_code=resp.status_code,
                url=issue_url,
            )

        msg = (
            f"GitHub issue creation failed: HTTP {resp.status_code} — {resp.text[:200]}"
        )
        logger.error(msg)
        return GitHubResult(ok=False, status_code=resp.status_code, url=url, error=msg)

    except Exception as exc:
        msg = f"GitHub API unreachable: {exc}"
        logger.error(msg)
        return GitHubResult(ok=False, error=msg)
