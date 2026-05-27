import logging
import time
from abc import ABC, abstractmethod

from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings
from launchmind.services.llm import call_llm


class Agent(ABC):
    def __init__(self, name: str, bus: MessageBus, settings: Settings):
        self.name = name
        self.bus = bus
        self.settings = settings
        self._running = False
        self.logger = logging.getLogger(f"launchmind.agents.{name}")

    @abstractmethod
    def handle_message(self, message: Message) -> None:
        ...

    def send_message(
        self,
        to: str,
        msg_type: MessageType,
        payload: dict,
        parent_id: str | None = None,
    ) -> Message:
        msg = Message(
            from_agent=self.name,
            to_agent=to,
            message_type=msg_type,
            payload=payload,
            parent_message_id=parent_id,
        )
        self.bus.send(msg)
        return msg

    def listen(self, poll_interval: float = 1.0) -> None:
        self._running = True
        self.logger.info("Listening for messages")
        while self._running:
            messages = self.bus.receive(self.name)
            for msg in messages:
                self.handle_message(msg)
            time.sleep(poll_interval)

    def stop(self) -> None:
        self._running = False
        self.logger.info("Stopped listening")

    def call_llm(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return call_llm(
            system_prompt,
            user_prompt,
            api_key=self.settings.DEEPSEEK_API_KEY,
            **kwargs,
        )
