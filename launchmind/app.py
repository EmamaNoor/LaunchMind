import json
import sys
import logging
import threading

from launchmind.config import Settings
from launchmind.logging_config import setup_logging
from launchmind.bus.transport import MessageBus
from launchmind.agents.ceo import CEOAgent
from launchmind.agents.product import ProductAgent
from launchmind.agents.engineer import EngineerAgent
from launchmind.agents.marketing import MarketingAgent
from launchmind.agents.qa import QAAgent

logger = logging.getLogger(__name__)


def run_pipeline(idea: str, settings: Settings | None = None) -> dict:
    if settings is None:
        settings = Settings()

    bus = MessageBus(settings.UPSTASH_REDIS_URL)
    bus.clear()

    logger.info("LaunchMind starting with idea: %s", idea)

    ceo = CEOAgent(bus, settings)
    agents = [
        ProductAgent(bus, settings),
        EngineerAgent(bus, settings),
        MarketingAgent(bus, settings),
        QAAgent(bus, settings),
    ]
    for agent in agents:
        threading.Thread(target=agent.listen, daemon=True).start()

    summary = ceo.run(idea)

    for agent in agents:
        agent.stop()

    return summary


def main():
    setup_logging()

    if len(sys.argv) < 2:
        print("Usage: python -m launchmind \"Your startup idea here\"")
        sys.exit(1)

    idea = sys.argv[1]
    summary = run_pipeline(idea)
    _print_summary(summary)


def _print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("PRODUCT SPEC")
    print("=" * 60)
    print(json.dumps(summary["phases"].get("product", {}), indent=2))

    print("\n" + "=" * 60)
    print("ENGINEER OUTPUT")
    print("=" * 60)
    eng = summary["phases"].get("engineer", {})
    print(f"PR:     {eng.get('pr_url', 'N/A')}")
    print(f"Issue:  {eng.get('issue_url', 'N/A')}")
    print(f"Vercel: {eng.get('vercel_url', 'N/A')}")

    print("\n" + "=" * 60)
    print("MARKETING COPY")
    print("=" * 60)
    mkt = summary["phases"].get("marketing", {})
    print(f"Tagline:     {mkt.get('tagline', '')}")
    print(f"Description: {mkt.get('description', '')}")
    social = mkt.get("social_posts", {})
    print(f"Twitter:     {social.get('twitter', '')}")
    cold = mkt.get("cold_email", {})
    print(f"Email Subj:  {cold.get('subject', '')}")

    print("\n" + "=" * 60)
    print("QA VERDICT")
    print("=" * 60)
    qa = summary["phases"].get("qa", {})
    print(f"Verdict: {qa.get('verdict', 'N/A').upper()}")
    print(f"Summary: {qa.get('summary', '')}")
    if qa.get("review_url"):
        print(f"Review:  {qa['review_url']}")
    issues = qa.get("issues", [])
    if issues:
        print("\nIssues:")
        for issue in issues:
            sev = issue.get("severity", "minor").upper()
            desc = issue.get("description", "")
            line = issue.get("line")
            loc = f" (line {line})" if line else ""
            print(f"  [{sev}]{loc} {desc}")
