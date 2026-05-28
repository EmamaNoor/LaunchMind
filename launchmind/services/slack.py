import logging

import requests

from launchmind.utils import retry

logger = logging.getLogger(__name__)

SLACK_API_URL = "https://slack.com/api/chat.postMessage"


@retry(max_attempts=3, delay=1.0)
def post_message(token: str, channel: str, blocks: list) -> None:
    r = requests.post(
        SLACK_API_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel, "blocks": blocks},
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
    logger.info("Posted to Slack channel %s", channel)
