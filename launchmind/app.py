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

    agents = [product, engineer]
    threads = []
    for agent in agents:
        t = threading.Thread(target=agent.listen, daemon=True)
        t.start()
        threads.append(t)

    tasks = ceo._decompose_idea(idea)
    logger.info("CEO decomposed idea into %d agent tasks", len(tasks))

    task_msg = ceo._dispatch_task("product", tasks["product_task"])
    product_result = ceo._wait_and_review("product", task_msg.message_id)

    print("\n" + "=" * 60)
    print("PRODUCT SPEC (approved by CEO)")
    print("=" * 60)
    print(json.dumps(product_result.payload, indent=2))

    product_spec = product_result.payload
    ceo._dispatch_task(
        "engineer",
        {"spec": product_spec, **tasks.get("engineer_task", {})},
    )
    engineer_result = ceo._wait_for("engineer")

    print("\n" + "=" * 60)
    print("ENGINEER OUTPUT")
    print("=" * 60)
    print(json.dumps(engineer_result.payload, indent=2))

    for agent in agents:
        agent.stop()
