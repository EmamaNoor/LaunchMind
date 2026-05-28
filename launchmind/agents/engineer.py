import json
import logging

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings
from launchmind.services import github

logger = logging.getLogger(__name__)

BRANCH_NAME = "agent-landing-page"

HTML_SYSTEM = """You are a senior frontend engineer. Generate a complete, production-ready HTML landing page based on the product spec provided.

Requirements:
- Single HTML file with embedded CSS (no external dependencies)
- Professional, modern design with clean typography
- Hero section with headline and subheadline based on the value proposition
- Features section showcasing each feature from the spec
- Call-to-action button
- Responsive design that works on mobile
- Use a cohesive color scheme

Return ONLY the raw HTML code. No markdown, no code fences, no explanation."""

ISSUE_SYSTEM = """You are a senior engineer. Write a GitHub issue description for creating an initial landing page.

Return ONLY the issue body text in markdown format. No code fences wrapping it. Include:
- What the page should contain
- Key sections
- Design requirements
Keep it concise (under 200 words)."""

PR_SYSTEM = """You are a senior engineer. Write a pull request title and body for a landing page implementation.

Respond with ONLY valid JSON (no markdown, no code fences):
{
  "title": "Short PR title",
  "body": "PR description in markdown"
}"""


class EngineerAgent(Agent):
    def __init__(self, bus: MessageBus, settings: Settings):
        super().__init__("engineer", bus, settings)

    def handle_message(self, message: Message) -> None:
        if message.message_type == MessageType.TASK:
            spec = message.payload.get("spec", message.payload)
            result = self._build_and_deploy(spec)
            self.send_message(
                "ceo",
                MessageType.RESULT,
                result,
                parent_id=message.message_id,
            )

        elif message.message_type == MessageType.REVISION_REQUEST:
            feedback = message.payload.get("feedback", "")
            original = message.payload.get("original", {})
            spec = original.get("spec", original)
            result = self._build_and_deploy(spec, feedback=str(feedback))
            self.send_message(
                "ceo",
                MessageType.RESULT,
                result,
                parent_id=message.message_id,
            )

    def _build_and_deploy(self, spec: dict, feedback: str | None = None) -> dict:
        html = self._generate_landing_page(spec, feedback)

        token = self.settings.GITHUB_TOKEN
        repo = self.settings.GITHUB_LANDING_REPO

        issue_body = self._generate_issue_description(spec)
        issue_url = github.create_issue(token, repo, "Initial landing page", issue_body)

        sha = github.get_default_branch_sha(token, repo)
        github.create_branch(token, repo, BRANCH_NAME, sha)
        github.commit_file(
            token, repo, "index.html", html,
            "Add landing page", BRANCH_NAME,
        )

        pr_info = self._generate_pr_info(spec)
        pr_url = github.create_pr(
            token, repo, pr_info["title"], pr_info["body"], BRANCH_NAME,
        )

        self.logger.info("Deployed: issue=%s pr=%s", issue_url, pr_url)
        return {
            "pr_url": pr_url,
            "issue_url": issue_url,
            "branch": BRANCH_NAME,
        }

    def _generate_landing_page(self, spec: dict, feedback: str | None = None) -> str:
        self.logger.info("Generating HTML landing page")
        prompt = f"Product spec:\n{json.dumps(spec, indent=2)}"
        if feedback:
            prompt += f"\n\nRevision feedback:\n{feedback}"
        return self.call_llm(HTML_SYSTEM, prompt)

    def _generate_issue_description(self, spec: dict) -> str:
        prompt = f"Product spec:\n{json.dumps(spec, indent=2)}"
        return self.call_llm(ISSUE_SYSTEM, prompt)

    def _generate_pr_info(self, spec: dict) -> dict:
        prompt = f"Product spec:\n{json.dumps(spec, indent=2)}"
        raw = self.call_llm(PR_SYSTEM, prompt)
        try:
            return self._parse_json(raw)
        except (json.JSONDecodeError, ValueError):
            value_prop = spec.get("value_proposition", spec.get("value_production", "landing page"))
            return {
                "title": "Add AI-generated landing page",
                "body": f"Auto-generated landing page for: {value_prop}",
            }

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
