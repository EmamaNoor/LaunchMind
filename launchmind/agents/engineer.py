import json
import logging
import re

from launchmind.agents.base import Agent
from launchmind.bus.models import Message, MessageType
from launchmind.bus.transport import MessageBus
from launchmind.config import Settings
from launchmind.services import github, vercel

logger = logging.getLogger(__name__)

HTML_SYSTEM = """You are a senior frontend engineer. Generate a single-file HTML landing page using EXACTLY the design system below. Do not deviate from these CSS values.

USE THIS EXACT CSS FOUNDATION — do not change these values:

:root {
  --bg: #ffffff;
  --bg-subtle: #f7f7f7;
  --border: #e5e5e5;
  --text-primary: #111111;
  --text-secondary: #555555;
  --text-muted: #888888;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  --radius: 8px;
  --max-width: 1080px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font); background: var(--bg); color: var(--text-primary); font-size: 16px; line-height: 1.6; -webkit-font-smoothing: antialiased; }
.container { max-width: var(--max-width); margin: 0 auto; padding: 0 24px; }

/* Nav */
nav { border-bottom: 1px solid var(--border); padding: 18px 0; }
nav .container { display: flex; align-items: center; justify-content: space-between; }
nav .logo { font-size: 17px; font-weight: 700; color: var(--text-primary); text-decoration: none; }
nav .btn-nav { background: var(--accent); color: #fff; padding: 9px 20px; border-radius: var(--radius); font-size: 14px; font-weight: 600; text-decoration: none; border: none; cursor: pointer; }
nav .btn-nav:hover { background: var(--accent-hover); }

/* Hero */
.hero { padding: 96px 0 80px; text-align: center; }
.hero h1 { font-size: 52px; font-weight: 700; line-height: 1.15; letter-spacing: -0.02em; color: var(--text-primary); max-width: 720px; margin: 0 auto 20px; }
.hero p { font-size: 19px; color: var(--text-secondary); max-width: 520px; margin: 0 auto 36px; line-height: 1.6; }
.btn-primary { display: inline-block; background: var(--accent); color: #fff; padding: 13px 28px; border-radius: var(--radius); font-size: 16px; font-weight: 600; text-decoration: none; border: none; cursor: pointer; }
.btn-primary:hover { background: var(--accent-hover); }

/* Features */
.features { padding: 80px 0; background: var(--bg-subtle); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.features h2 { font-size: 28px; font-weight: 700; text-align: center; margin-bottom: 48px; letter-spacing: -0.01em; }
.features-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.feature-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px 24px; }
.feature-card h3 { font-size: 15px; font-weight: 700; margin-bottom: 8px; color: var(--text-primary); }
.feature-card p { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }

/* Footer */
footer { padding: 40px 0; text-align: center; }
footer .logo { font-size: 15px; font-weight: 700; color: var(--text-primary); }
footer p { font-size: 13px; color: var(--text-muted); margin-top: 6px; }

/* Responsive */
@media (max-width: 768px) {
  .hero h1 { font-size: 34px; }
  .hero p { font-size: 16px; }
  .features-grid { grid-template-columns: 1fr; }
}

REQUIRED HTML STRUCTURE (4 sections, in this order):
1. <nav> — logo (product name) left, one "Get Started" button right
2. <section class="hero"> — h1 headline, p subheadline, one CTA button
3. <section class="features"> — h2 title, grid of feature cards (one per feature in spec)
4. <footer> — logo + tagline

STRICT RULES:
- Use ONLY the CSS variables and classes defined above. No extra colors, fonts, or sizes.
- No gradients, shadows, animations, icons, emojis, or images.
- No inline styles except where a CSS class genuinely cannot cover it.
- Never use em dashes (—). Use commas or periods instead.
- No AI filler words: "revolutionize", "game-changer", "seamless", "cutting-edge", "empower", "unlock", "streamline", "harness", "supercharge".
- No placeholder text like [Name], [Company], [Date].
- Write copy like a human: direct, specific, plain English.

Return ONLY the raw HTML. No markdown, no code fences, no explanation."""

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
