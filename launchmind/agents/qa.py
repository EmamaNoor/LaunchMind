import json
import logging

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings
from launchmind.services import github

logger = logging.getLogger(__name__)

QA_SYSTEM = """You are a senior QA engineer reviewing a product launch. You receive:
1. Product spec (source of truth)
2. HTML landing page (with line numbers)
3. Marketing copy

Review for:
- HTML: valid structure, responsive design, accessibility (alt text, semantic HTML), SEO basics (title tag, meta description), alignment with product spec features
- Copy: consistency with product spec, clear CTAs, appropriate tone per channel
- Consistency: landing page and marketing copy should tell the same story

Respond with ONLY valid JSON (no markdown, no code fences):
{
  "verdict": "pass" or "fail",
  "summary": "2-3 sentence overall assessment",
  "issues": [
    {
      "type": "html" or "copy",
      "severity": "critical" or "minor",
      "line": <line number for html issues, null for copy issues>,
      "description": "What is wrong and how to fix it"
    }
  ]
}

Always identify at least 2 areas for improvement even if overall verdict is pass.
Only set verdict to "fail" for critical issues that would hurt user experience or contradict the product spec."""


class QAAgent(Agent):
    def __init__(self, bus: MessageBus, settings: Settings):
        super().__init__("qa", bus, settings)

    def handle_message(self, message: Message) -> None:
        if message.message_type != MessageType.TASK:
            return

        payload = message.payload
        engineer_output = payload.get("engineer_output", {})
        marketing_output = payload.get("marketing_output", {})
        product_spec = payload.get("product_spec", {})

        html = self._fetch_html(engineer_output)
        review = self._review_all(product_spec, html, marketing_output)

        review_url = None
        pr_url = engineer_output.get("pr_url", "")
        if pr_url:
            review_url = self._post_github_review(review, pr_url, engineer_output)

        result = {
            "verdict": review.get("verdict", "fail"),
            "summary": review.get("summary", ""),
            "issues": review.get("issues", []),
            "review_url": review_url,
        }
        self.send_message("ceo", MessageType.RESULT, result, parent_id=message.message_id)

    def _review_all(self, spec: dict, html: str | None, marketing_copy: dict) -> dict:
        self.logger.info("Running QA review")
        numbered_html = ""
        if html:
            lines = html.splitlines()
            numbered_html = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))

        prompt = (
            f"Product spec:\n{json.dumps(spec, indent=2)}\n\n"
            f"HTML landing page:\n{numbered_html or '(not available)'}\n\n"
            f"Marketing copy:\n{json.dumps(marketing_copy, indent=2)}"
        )
        raw = self.call_llm(QA_SYSTEM, prompt, max_tokens=2048)
        try:
            review = self._parse_json(raw)
        except (json.JSONDecodeError, ValueError):
            self.logger.warning("QA LLM returned malformed JSON, using fallback")
            review = {
                "verdict": "fail",
                "summary": "QA review could not be parsed.",
                "issues": [],
            }
        self.logger.info("QA verdict: %s", review.get("verdict"))
        return review

    def _fetch_html(self, engineer_output: dict) -> str | None:
        branch = engineer_output.get("branch", "")
        if not branch:
            return None
        try:
            return github.get_file_content(
                self.settings.GITHUB_TOKEN,
                self.settings.GITHUB_LANDING_REPO,
                "index.html",
                branch,
            )
        except Exception:
            self.logger.exception("Could not fetch HTML from GitHub — reviewing copy only")
            return None

    def _post_github_review(self, review: dict, pr_url: str, engineer_output: dict) -> str | None:
        try:
            pr_number = int(pr_url.rstrip("/").split("/")[-1])
            branch = engineer_output.get("branch", "agent-landing-page")
            commit_id = github.get_default_branch_sha(
                self.settings.GITHUB_TOKEN,
                self.settings.GITHUB_LANDING_REPO,
                branch=branch,
            )

            issues = review.get("issues", [])
            verdict = review.get("verdict", "pass")
            event = "REQUEST_CHANGES" if verdict == "fail" else "COMMENT"

            inline_comments = []
            body_lines = [review.get("summary", ""), ""]
            for issue in issues:
                line = issue.get("line")
                desc = f"**[{issue.get('severity', 'minor').upper()}]** {issue.get('description', '')}"
                if issue.get("type") == "html" and isinstance(line, int) and line > 0:
                    inline_comments.append({
                        "path": "index.html",
                        "line": line,
                        "side": "RIGHT",
                        "body": desc,
                    })
                else:
                    body_lines.append(f"- {desc}")

            body = "\n".join(body_lines).strip()
            return github.create_review(
                self.settings.GITHUB_TOKEN,
                self.settings.GITHUB_LANDING_REPO,
                pr_number,
                commit_id,
                body,
                event,
                inline_comments,
            )
        except Exception:
            self.logger.exception("GitHub review post failed — continuing")
            return None

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
