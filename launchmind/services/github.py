import base64
import logging

import requests

from launchmind.utils import retry

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


@retry(max_attempts=3, delay=1.0)
def get_default_branch_sha(token: str, repo: str, branch: str = "main") -> str:
    r = requests.get(
        f"{API_BASE}/repos/{repo}/git/ref/heads/{branch}",
        headers=_headers(token),
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


@retry(max_attempts=3, delay=1.0)
def create_branch(token: str, repo: str, branch_name: str, sha: str) -> None:
    r = requests.post(
        f"{API_BASE}/repos/{repo}/git/refs",
        headers=_headers(token),
        json={"ref": f"refs/heads/{branch_name}", "sha": sha},
    )
    if r.status_code == 422:
        logger.info("Branch %s already exists, updating to latest SHA", branch_name)
        r2 = requests.patch(
            f"{API_BASE}/repos/{repo}/git/refs/heads/{branch_name}",
            headers=_headers(token),
            json={"sha": sha, "force": True},
        )
        r2.raise_for_status()
    else:
        r.raise_for_status()
    logger.info("Created branch: %s", branch_name)


@retry(max_attempts=3, delay=1.0)
def commit_file(
    token: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str,
    author_name: str = "EngineerAgent",
    author_email: str = "agent@launchmind.ai",
) -> None:
    encoded = base64.b64encode(content.encode()).decode()
    payload: dict = {
        "message": message,
        "content": encoded,
        "branch": branch,
        "committer": {"name": author_name, "email": author_email},
    }
    # If file already exists on the branch, include its SHA to update it
    existing = requests.get(
        f"{API_BASE}/repos/{repo}/contents/{path}",
        headers=_headers(token),
        params={"ref": branch},
    )
    if existing.status_code == 200:
        payload["sha"] = existing.json()["sha"]

    r = requests.put(
        f"{API_BASE}/repos/{repo}/contents/{path}",
        headers=_headers(token),
        json=payload,
    )
    r.raise_for_status()
    logger.info("Committed %s to %s", path, branch)


@retry(max_attempts=3, delay=1.0)
def create_issue(token: str, repo: str, title: str, body: str) -> str:
    r = requests.post(
        f"{API_BASE}/repos/{repo}/issues",
        headers=_headers(token),
        json={"title": title, "body": body},
    )
    r.raise_for_status()
    url = r.json()["html_url"]
    logger.info("Created issue: %s", url)
    return url


@retry(max_attempts=3, delay=1.0)
def create_pr(
    token: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str = "main",
) -> str:
    r = requests.post(
        f"{API_BASE}/repos/{repo}/pulls",
        headers=_headers(token),
        json={"title": title, "body": body, "head": head, "base": base},
    )
    if r.status_code == 422:
        # PR already exists — fetch and return its URL
        existing = requests.get(
            f"{API_BASE}/repos/{repo}/pulls",
            headers=_headers(token),
            params={"head": head, "state": "open"},
        )
        existing.raise_for_status()
        pulls = existing.json()
        if pulls:
            url = pulls[0]["html_url"]
            logger.info("PR already exists: %s", url)
            return url
    r.raise_for_status()
    url = r.json()["html_url"]
    logger.info("Created PR: %s", url)
    return url


@retry(max_attempts=3, delay=1.0)
def get_file_content(token: str, repo: str, path: str, branch: str) -> str:
    import base64
    r = requests.get(
        f"{API_BASE}/repos/{repo}/contents/{path}",
        headers=_headers(token),
        params={"ref": branch},
    )
    r.raise_for_status()
    return base64.b64decode(r.json()["content"]).decode()


@retry(max_attempts=3, delay=1.0)
def create_review(
    token: str,
    repo: str,
    pr_number: int,
    commit_id: str,
    body: str,
    event: str,
    comments: list,
) -> str:
    r = requests.post(
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/reviews",
        headers=_headers(token),
        json={
            "commit_id": commit_id,
            "body": body,
            "event": event,
            "comments": comments,
        },
    )
    r.raise_for_status()
    url = r.json()["html_url"]
    logger.info("Posted PR review on #%d: %s", pr_number, url)
    return url


@retry(max_attempts=3, delay=1.0)
def post_review_comment(
    token: str,
    repo: str,
    pr_number: int,
    commit_id: str,
    body: str,
    path: str,
    position: int = 1,
) -> None:
    r = requests.post(
        f"{API_BASE}/repos/{repo}/pulls/{pr_number}/comments",
        headers=_headers(token),
        json={"body": body, "path": path, "position": position, "commit_id": commit_id},
    )
    r.raise_for_status()
    logger.info("Posted review comment on PR #%d", pr_number)
