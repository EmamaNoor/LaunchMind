import logging

import requests

from launchmind.utils import retry

logger = logging.getLogger(__name__)

VERCEL_API_URL = "https://api.vercel.com/v13/deployments"


@retry(max_attempts=3, delay=1.0)
def deploy_static(token: str, html_content: str, project_name: str = "launchmind-landing") -> str:
    r = requests.post(
        VERCEL_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
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
    url = f"https://{project_name}.vercel.app"
    logger.info("Deployed to Vercel: %s", url)
    return url
