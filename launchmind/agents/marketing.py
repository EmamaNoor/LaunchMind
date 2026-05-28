import json
import logging

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings
from launchmind.services import slack, email

logger = logging.getLogger(__name__)

COPY_SYSTEM = """You are a senior growth marketer. Given a product spec, generate compelling marketing copy.

IMPORTANT: Never use placeholder brackets like [YOUR NAME], [COMPANY], [DATE], etc. Write fully completed copy ready to send as-is. Sign emails as "The {product name} Team".

Respond with ONLY valid JSON (no markdown, no code fences):
{
  "tagline": "Under 10 words. Punchy and memorable.",
  "description": "2-3 sentences describing the product clearly.",
  "cold_email": {
    "subject": "Email subject line",
    "body": "Cold outreach email body targeting a potential user or investor. 3-4 short paragraphs. Include a clear CTA. Sign off as The [Product] Team — use the actual product name, no brackets."
  },
  "social_posts": {
    "twitter": "Under 280 chars. Hook + value + CTA.",
    "linkedin": "Professional tone. 3-4 sentences. Value-focused.",
    "instagram": "Casual, visual tone. Emojis OK. 2-3 sentences + hashtags."
  }
}"""


class MarketingAgent(Agent):
    def __init__(self, bus: MessageBus, settings: Settings):
        super().__init__("marketing", bus, settings)

    def handle_message(self, message: Message) -> None:
        if message.message_type == MessageType.TASK:
            spec = message.payload
            copy = self._generate_copy(spec)
            self._send_cold_email(copy)
            self._post_to_slack(copy)
            self.send_message("ceo", MessageType.RESULT, copy, parent_id=message.message_id)

        elif message.message_type == MessageType.REVISION_REQUEST:
            feedback = message.payload.get("feedback", "")
            original_spec = message.payload.get("original", {})
            copy = self._generate_copy(original_spec, feedback=str(feedback))
            self._send_cold_email(copy)
            self._post_to_slack(copy)
            self.send_message("ceo", MessageType.RESULT, copy, parent_id=message.message_id)

    def _generate_copy(self, spec: dict, feedback: str | None = None) -> dict:
        self.logger.info("Generating marketing copy")
        prompt = f"Product spec:\n{json.dumps(spec, indent=2)}"
        if feedback:
            prompt += f"\n\nRevision feedback:\n{feedback}"
        raw = self.call_llm(COPY_SYSTEM, prompt)
        try:
            copy = self._parse_json(raw)
        except (json.JSONDecodeError, ValueError):
            self.logger.warning("LLM returned malformed JSON, using fallback copy")
            value_prop = spec.get("value_proposition", spec.get("value_production", "our product"))
            copy = {
                "tagline": value_prop[:60],
                "description": value_prop,
                "cold_email": {"subject": "Exciting new product", "body": value_prop},
                "social_posts": {"twitter": value_prop, "linkedin": value_prop, "instagram": value_prop},
            }
        self.logger.info("Generated copy with tagline: %s", copy.get("tagline", ""))
        return copy

    def _post_to_slack(self, copy: dict, pr_url: str = "") -> None:
        tagline = copy.get("tagline", "New launch")
        description = copy.get("description", "")
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"New Launch: {tagline}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": description},
            },
        ]
        if pr_url:
            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*GitHub PR:* <{pr_url}|View PR>"},
                    {"type": "mrkdwn", "text": "*Status:* Ready for review"},
                ],
            })
        try:
            slack.post_message(
                self.settings.SLACK_BOT_TOKEN,
                self.settings.SLACK_CHANNEL,
                blocks,
            )
        except Exception:
            self.logger.exception("Slack post failed — continuing")

    def _send_cold_email(self, copy: dict) -> None:
        cold_email = copy.get("cold_email", {})
        subject = cold_email.get("subject", "Exciting new product launch")
        body = cold_email.get("body", copy.get("description", ""))
        try:
            email.send_email(
                self.settings.SENDGRID_API_KEY,
                self.settings.SENDGRID_FROM_EMAIL,
                self.settings.TEST_EMAIL,
                subject,
                body,
            )
        except Exception:
            self.logger.exception("Email send failed — continuing")

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
