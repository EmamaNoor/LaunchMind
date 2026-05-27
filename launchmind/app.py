import sys
import logging

from launchmind.config import Settings
from launchmind.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main():
    setup_logging()

    if len(sys.argv) < 2:
        print("Usage: python -m launchmind \"Your startup idea here\"")
        sys.exit(1)

    idea = sys.argv[1]
    settings = Settings()
    logger.info("LaunchMind starting with idea: %s", idea)
