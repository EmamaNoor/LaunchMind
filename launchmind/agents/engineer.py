import json
import logging
import re

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings
from launchmind.services import github, vercel

logger = logging.getLogger(__name__)

HTML_SYSTEM = """You are a senior software engineer. Generate a clean, professional, modern single-file HTML landing page for the given startup idea. Use the product spec provided to populate all content. Inline all CSS. No external dependencies. No empty fields. No placeholder text. The page should look like something a real startup would ship.

The page must include:
- A hero section with a short, punchy headline and a one-sentence subheadline
- A features section listing the product's key features
- A "How it Works" section with 3 concise steps
- A call-to-action section with a button

Rules:
- All text content must come from the product spec. Never invent placeholder copy or leave fields empty.
- Do not include <form>, <input>, <textarea>, or <select> elements. This is a static marketing page.
- Inline all CSS inside a <style> tag in <head>. No external stylesheets or scripts.
- Output a complete valid HTML5 document starting with <!DOCTYPE html>.
- Never use em dashes (—). Use commas or periods instead.
- Never use AI filler words: "revolutionize", "game-changer", "seamless", "cutting-edge", "empower", "unlock", "streamline", "harness", "supercharge", "transformative", "innovative", "leverage", "synergy".
- Return ONLY the raw HTML. No markdown, no code fences, no explanation."""

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
        branch_name = self._make_branch_name(spec)

        slug = branch_name.removeprefix("landing/")
        vercel_url = self._deploy_to_vercel(html, slug)

        token = self.settings.GITHUB_TOKEN
        repo = self.settings.GITHUB_LANDING_REPO

        issue_body = self._generate_issue_description(spec)
        if vercel_url:
            issue_body += f"\n\n**Live Preview:** {vercel_url}"
        try:
            issue_url = github.create_issue(token, repo, "Initial landing page", issue_body)
        except Exception:
            self.logger.exception("GitHub issue creation failed — continuing without issue")
            issue_url = ""

        sha = github.get_default_branch_sha(token, repo)
        github.create_branch(token, repo, branch_name, sha)

        file_path = branch_name.removeprefix("landing/") + "/index.html"
        commit_msg = f"Live at: {vercel_url}" if vercel_url else "Add landing page"
        github.commit_file(
            token, repo, file_path, html,
            commit_msg, branch_name,
        )

        pr_info = self._generate_pr_info(spec)
        pr_body = pr_info["body"]
        if vercel_url:
            pr_body += f"\n\n---\n**Live Preview:** {vercel_url}"
        pr_url = github.create_pr(
            token, repo, pr_info["title"], pr_body, branch_name,
        )

        self.logger.info("Deployed: issue=%s pr=%s vercel=%s", issue_url, pr_url, vercel_url)
        return {
            "pr_url": pr_url,
            "issue_url": issue_url,
            "branch": branch_name,
            "file_path": file_path,
            "vercel_url": vercel_url,
        }

    def _make_branch_name(self, spec: dict) -> str:
        name = spec.get("name", spec.get("value_proposition", "landing"))
        slug = re.sub(r"[^a-z0-9]", "", name.lower())[:30]
        return f"landing/{slug}"

    def _deploy_to_vercel(self, html: str, project_name: str) -> str | None:
        if not self.settings.VERCEL_TOKEN:
            self.logger.warning("VERCEL_TOKEN not set — skipping Vercel deployment")
            return None
        try:
            return vercel.deploy_static(self.settings.VERCEL_TOKEN, html, project_name)
        except Exception:
            self.logger.exception("Vercel deployment failed — continuing")
            return None

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
