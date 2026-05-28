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

logger = logging.getLogger(__name__)


def main():
    setup_logging()

    if len(sys.argv) < 2:
        print("Usage: python -m launchmind \"Your startup idea here\"")
        sys.exit(1)

    idea = sys.argv[1]
    settings = Settings()
    bus = MessageBus(settings.UPSTASH_REDIS_URL)
    bus.clear()

    logger.info("LaunchMind starting with idea: %s", idea)

    ceo = CEOAgent(bus, settings)
    product = ProductAgent(bus, settings)
    engineer = EngineerAgent(bus, settings)
    marketing = MarketingAgent(bus, settings)

    agents = [product, engineer, marketing]
    for agent in agents:
        t = threading.Thread(target=agent.listen, daemon=True)
        t.start()

    tasks = ceo._decompose_idea(idea)
    logger.info("CEO decomposed idea into %d agent tasks", len(tasks))

    task_msg = ceo._dispatch_task("product", tasks["product_task"])
    product_result = ceo._wait_and_review("product", task_msg.message_id)

    print("\n" + "=" * 60)
    print("PRODUCT SPEC (approved by CEO)")
    print("=" * 60)
    print(json.dumps(product_result.payload, indent=2))

    product_spec = product_result.payload

    # Dispatch Engineer and Marketing in parallel
    ceo._dispatch_task(
        "engineer",
        {"spec": product_spec, **tasks.get("engineer_task", {})},
    )
    ceo._dispatch_task("marketing", product_spec)

    engineer_result = ceo._wait_for("engineer")
    marketing_result = ceo._wait_for("marketing")

    print("\n" + "=" * 60)
    print("ENGINEER OUTPUT")
    print("=" * 60)
    print(json.dumps(engineer_result.payload, indent=2))

    print("\n" + "=" * 60)
    print("MARKETING COPY (approved by CEO)")
    print("=" * 60)
    copy = marketing_result.payload
    print(f"Tagline:     {copy.get('tagline', '')}")
    print(f"Description: {copy.get('description', '')}")
    social = copy.get("social_posts", {})
    print(f"Twitter:     {social.get('twitter', '')}")
    print(f"LinkedIn:    {social.get('linkedin', '')}")
    cold = copy.get("cold_email", {})
    print(f"Email Subj:  {cold.get('subject', '')}")

    for agent in agents:
        agent.stop()
