import json
import time
import logging

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings

logger = logging.getLogger(__name__)

MAX_REVISION_ROUNDS = 2
POLL_INTERVAL = 2
POLL_TIMEOUT = 120

DECOMPOSE_SYSTEM = """You are the CEO of a startup. Your job is to take a startup idea and break it into concrete tasks for your team.

Your team has these agents:
- product: Defines product specs (personas, features, user stories)
- engineer: Builds an HTML landing page and opens a GitHub PR
- marketing: Creates tagline, description, cold email, social posts, posts to Slack
- qa: Reviews the engineer's code and marketing copy for quality

Respond with ONLY valid JSON (no markdown, no code fences) in this format:
{
  "product_task": {
    "idea": "<the startup idea>",
    "focus": "<specific instructions for the product agent>"
  },
  "engineer_task": {
    "focus": "<specific instructions for the engineer>"
  },
  "marketing_task": {
    "focus": "<specific instructions for the marketing agent>"
  },
  "qa_task": {
    "focus": "<specific instructions for the QA reviewer>"
  }
}"""

REVIEW_SYSTEM = """You are the CEO reviewing output from one of your agents. Evaluate the quality critically.

Respond with ONLY valid JSON (no markdown, no code fences):
{
  "approved": true or false,
  "reasoning": "<why you approved or rejected>",
  "feedback": "<specific feedback if rejected, empty string if approved>"
}"""


class CEOAgent(Agent):
    def __init__(self, bus: MessageBus, settings: Settings):
        super().__init__("ceo", bus, settings)
        self.decisions: list[dict] = []

    def handle_message(self, message: Message) -> None:
        pass

    def run(self, idea: str) -> dict:
        self.logger.info("Starting LaunchMind with idea: %s", idea)
        summary = {"idea": idea, "phases": {}, "decisions": self.decisions}

        tasks = self._decompose_idea(idea)
        summary["phases"]["decompose"] = tasks

        product_msg = self._dispatch_task(
            "product",
            tasks["product_task"],
        )

        product_result = self._wait_and_review(
            "product",
            product_msg.message_id,
        )
        summary["phases"]["product"] = product_result.payload

        product_spec = product_result.payload

        eng_msg = self._dispatch_task(
            "engineer",
            {"spec": product_spec, **tasks.get("engineer_task", {})},
        )
        mkt_msg = self._dispatch_task(
            "marketing",
            {"spec": product_spec, **tasks.get("marketing_task", {})},
        )

        engineer_result = self._wait_for("engineer")
        summary["phases"]["engineer"] = engineer_result.payload

        marketing_result = self._wait_for("marketing")
        summary["phases"]["marketing"] = marketing_result.payload

        qa_msg = self._dispatch_task(
            "qa",
            {
                "engineer_output": engineer_result.payload,
                "marketing_output": marketing_result.payload,
                "product_spec": product_spec,
                **tasks.get("qa_task", {}),
            },
        )

        qa_result = self._wait_for("qa")
        summary["phases"]["qa"] = qa_result.payload

        self._handle_qa_verdict(qa_result, engineer_result, marketing_result, summary)

        self.logger.info("LaunchMind run complete")
        self._log_decision("run_complete", "All phases finished", str(summary))
        summary["decisions"] = self.decisions
        return summary

    def _decompose_idea(self, idea: str) -> dict:
        self.logger.info("Decomposing idea into agent tasks")
        raw = self.call_llm(DECOMPOSE_SYSTEM, idea)
        tasks = self._parse_json(raw)
        self._log_decision(
            "decompose",
            f"Broke idea into {len(tasks)} agent tasks",
            str(tasks),
        )
        return tasks

    def _wait_and_review(
        self,
        agent_name: str,
        parent_msg_id: str,
    ) -> Message:
        for round_num in range(MAX_REVISION_ROUNDS + 1):
            result = self._wait_for(agent_name)

            approved, reasoning, feedback = self._review_output(
                agent_name,
                result.payload,
            )

            if approved:
                self._log_decision(
                    f"review_{agent_name}",
                    f"Approved {agent_name} output (round {round_num + 1})",
                    reasoning,
                )
                return result

            self._log_decision(
                f"revision_{agent_name}",
                f"Rejected {agent_name} output (round {round_num + 1})",
                reasoning,
            )

            if round_num < MAX_REVISION_ROUNDS:
                self.logger.info(
                    "Requesting revision from %s: %s", agent_name, feedback
                )
                self.send_message(
                    agent_name,
                    MessageType.REVISION_REQUEST,
                    {"feedback": feedback, "original": result.payload},
                    parent_id=result.message_id,
                )
            else:
                self.logger.warning(
                    "Max revisions reached for %s, proceeding with last output",
                    agent_name,
                )

        return result

    def _review_output(
        self,
        agent_name: str,
        output: dict,
    ) -> tuple[bool, str, str]:
        prompt = (
            f"Review this output from the {agent_name} agent:\n\n"
            f"{json.dumps(output, indent=2)}"
        )
        raw = self.call_llm(REVIEW_SYSTEM, prompt)
        review = self._parse_json(raw)
        return (
            review.get("approved", False),
            review.get("reasoning", ""),
            review.get("feedback", ""),
        )

    def _handle_qa_verdict(
        self,
        qa_result: Message,
        engineer_result: Message,
        marketing_result: Message,
        summary: dict,
    ) -> None:
        verdict = qa_result.payload.get("verdict", "pass")

        if verdict == "pass":
            self._log_decision("qa_verdict", "QA passed", str(qa_result.payload))
            return

        self._log_decision(
            "qa_verdict",
            "QA failed — determining which agent needs revision",
            str(qa_result.payload),
        )

        issues = qa_result.payload.get("issues", [])
        prompt = (
            f"QA found these issues:\n{json.dumps(issues, indent=2)}\n\n"
            "Which agent should revise: 'engineer', 'marketing', or 'both'? "
            "Respond with ONLY valid JSON: {\"revise\": \"engineer|marketing|both\", \"reasoning\": \"...\"}"
        )
        raw = self.call_llm(REVIEW_SYSTEM, prompt)
        decision = self._parse_json(raw)
        target = decision.get("revise", "both")

        if target in ("engineer", "both"):
            self.send_message(
                "engineer",
                MessageType.REVISION_REQUEST,
                {"feedback": issues, "original": engineer_result.payload},
                parent_id=engineer_result.message_id,
            )

        if target in ("marketing", "both"):
            self.send_message(
                "marketing",
                MessageType.REVISION_REQUEST,
                {"feedback": issues, "original": marketing_result.payload},
                parent_id=marketing_result.message_id,
            )

        summary["phases"]["qa_revision"] = {
            "target": target,
            "reasoning": decision.get("reasoning", ""),
        }

    def _dispatch_task(
        self,
        to: str,
        payload: dict,
        parent_id: str | None = None,
    ) -> Message:
        self.logger.info("Dispatching task to %s", to)
        return self.send_message(to, MessageType.TASK, payload, parent_id)

    def _wait_for(self, agent_name: str) -> Message:
        self.logger.info("Waiting for response from %s", agent_name)
        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            messages = self.bus.receive("ceo")
            for msg in messages:
                if msg.from_agent == agent_name:
                    self.logger.info("Received response from %s", agent_name)
                    return msg
                self.bus.send(msg)
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        raise TimeoutError(f"Timed out waiting for response from {agent_name}")

    def _log_decision(self, phase: str, summary: str, details: str) -> None:
        decision = {"phase": phase, "summary": summary, "details": details}
        self.decisions.append(decision)
        self.logger.info("Decision [%s]: %s", phase, summary)

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
