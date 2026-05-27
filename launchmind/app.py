import json
import sys
import logging
import threading

from launchmind.config import Settings
from launchmind.logging_config import setup_logging
from launchmind.bus.transport import MessageBus
from launchmind.agents.ceo import CEOAgent
from launchmind.agents.product import ProductAgent

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

    product_thread = threading.Thread(target=product.listen, daemon=True)
    product_thread.start()

    tasks = ceo._decompose_idea(idea)
    logger.info("CEO decomposed idea into %d agent tasks", len(tasks))

    task_msg = ceo._dispatch_task("product", tasks["product_task"])

    product_result = ceo._wait_and_review("product", task_msg.message_id)

    product.stop()

    print("\n" + "=" * 60)
    print("PRODUCT SPEC (approved by CEO)")
    print("=" * 60)
    print(json.dumps(product_result.payload, indent=2))
