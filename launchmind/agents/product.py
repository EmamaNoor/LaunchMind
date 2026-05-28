import json
import logging

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings

logger = logging.getLogger(__name__)

SPEC_SYSTEM = """You are a senior product manager. Given a startup idea and focus areas, generate a detailed product specification.

Respond with ONLY valid JSON (no markdown, no code fences) in this exact format:
{
  "value_proposition": "One sentence: what the product does and for whom",
  "personas": [
    {"name": "Persona Name", "role": "Their role", "pain_point": "Their main pain point"}
  ],
  "features": [
    {"name": "Feature Name", "description": "What it does", "priority": 1}
  ],
  "user_stories": [
    "As a [persona], I want [action], so that [benefit]"
  ]
}

Include at least 3 personas, 5 features (priority 1=highest), and 3 user stories."""


class ProductAgent(Agent):
    def __init__(self, bus: MessageBus, settings: Settings):
        super().__init__("product", bus, settings)

    def handle_message(self, message: Message) -> None:
        if message.message_type == MessageType.TASK:
            idea = message.payload.get("idea", "")
            focus = message.payload.get("focus", "")
            spec = self._generate_spec(idea, focus)
            self._distribute_spec(spec, message.message_id)

        elif message.message_type == MessageType.REVISION_REQUEST:
            feedback = message.payload.get("feedback", "")
            original = message.payload.get("original", {})
            idea = original.get("idea", "")
            focus = original.get("focus", "")
            spec = self._generate_spec(idea, focus, feedback)
            self._distribute_spec(spec, message.message_id)

    def _generate_spec(
        self,
        idea: str,
        focus: str,
        feedback: str | None = None,
    ) -> dict:
        self.logger.info("Generating product spec")
        prompt = f"Startup idea: {idea}\nFocus areas: {focus}"
        if feedback:
            prompt += f"\n\nPrevious attempt was rejected. Address this feedback:\n{feedback}"

        raw = self.call_llm(SPEC_SYSTEM, prompt)
        spec = self._parse_json(raw)
        self.logger.info(
            "Generated spec with %d personas, %d features, %d stories",
            len(spec.get("personas", [])),
            len(spec.get("features", [])),
            len(spec.get("user_stories", [])),
        )
        return spec

    def _distribute_spec(self, spec: dict, parent_id: str) -> None:
        self.send_message("engineer", MessageType.RESULT, spec, parent_id)
        self.send_message("ceo", MessageType.RESULT, spec, parent_id)
        self.logger.info("Spec sent to engineer and ceo")

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
