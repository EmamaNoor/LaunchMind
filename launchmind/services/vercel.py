import logging

import requests

from launchmind.utils import retry

logger = logging.getLogger(__name__)

VERCEL_API_URL = "https://api.vercel.com/v13/deployments"


@retry(max_attempts=3, delay=1.0)
def deploy_static(token: str, html_content: str, project_name: str = "launchmind-landing") -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = requests.post(
        VERCEL_API_URL,
        headers=headers,
        json={
            "name": project_name,
            "files": [
                {"file": "index.html", "data": html_content},
            ],
            "projectSettings": {"framework": None},
            "target": "production",
        },
    )
    r.raise_for_status()
    data = r.json()
    deployment_id = data["id"]
    raw_url = f"https://{data['url']}"

    # Disable Vercel Authentication (Deployment Protection) for the project
    # to ensure the landing pages are publicly accessible without login/requesting access
    try:
        patch_url = f"https://api.vercel.com/v9/projects/{project_name}"
        pr = requests.patch(
            patch_url,
            headers=headers,
            json={
                "ssoProtection": None,
                "passwordProtection": None,
            },
        )
        if pr.ok:
            logger.info("Successfully disabled Vercel Authentication / Deployment Protection for project %s", project_name)
        else:
            logger.warning(
                "Failed to disable Vercel Authentication for project %s: %s %s",
                project_name, pr.status_code, pr.text
            )
    except Exception as e:
        logger.exception("Error while trying to disable Vercel Authentication for project %s: %s", project_name, e)

    alias = f"{project_name}.vercel.app"
    ar = requests.post(
        f"https://api.vercel.com/v2/deployments/{deployment_id}/aliases",
        headers=headers,
        json={"alias": alias},
    )
    if ar.ok:
        url = f"https://{alias}"
    else:
        logger.warning("Alias %s failed (%s) — using deployment URL", alias, ar.status_code)
        url = raw_url
    logger.info("Deployed to Vercel: %s", url)
    return url
