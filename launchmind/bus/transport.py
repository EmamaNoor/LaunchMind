import logging

import redis

from launchmind.bus.models import Message

logger = logging.getLogger(__name__)

INBOX_PREFIX = "launchmind:inbox:"
HISTORY_KEY = "launchmind:history"


class MessageBus:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def send(self, message: Message) -> None:
        data = message.to_json()
        inbox_key = f"{INBOX_PREFIX}{message.to_agent}"
        self._redis.rpush(inbox_key, data)
        self._redis.rpush(HISTORY_KEY, data)
        logger.info(
            "%s -> %s [%s] %s",
            message.from_agent,
            message.to_agent,
            message.message_type.value,
            message.message_id,
        )

    def receive(self, agent_name: str) -> list[Message]:
        inbox_key = f"{INBOX_PREFIX}{agent_name}"
        raw_messages = self._redis.lrange(inbox_key, 0, -1)
        self._redis.delete(inbox_key)
        return [Message.from_json(raw) for raw in raw_messages]

    def get_history(self) -> list[Message]:
        raw_messages = self._redis.lrange(HISTORY_KEY, 0, -1)
        return [Message.from_json(raw) for raw in raw_messages]

    def clear(self) -> None:
        keys = self._redis.keys("launchmind:*")
        if keys:
            self._redis.delete(*keys)
        logger.info("Message bus cleared")
