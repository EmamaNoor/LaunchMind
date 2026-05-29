<div align="center">

# LaunchMind

**Multi-agent AI system that turns a startup idea into real-world outputs in under 2 minutes**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFF?logo=openai&logoColor=white)](https://platform.deepseek.com)
[![Redis](https://img.shields.io/badge/Upstash-Redis-DC382D?logo=redis&logoColor=white)](https://upstash.com)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![SendGrid](https://img.shields.io/badge/SendGrid-Email-1A82E2?logo=twilio&logoColor=white)](https://sendgrid.com)
[![Slack](https://img.shields.io/badge/Slack-Bot-4A154B?logo=slack&logoColor=white)](https://api.slack.com)

Give it a startup idea. Five AI agents collaborate to produce a product spec, a deployed landing page with a GitHub PR, cold outreach emails, Slack announcements, and a QA code review. All autonomously.

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [Example Output](#example-output)
- [Viewing the Landing Page](#viewing-the-landing-page)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

LaunchMind is a custom multi-agent system. No frameworks like CrewAI or LangGraph. Five specialized AI agents communicate through a Redis message bus, each producing tangible, real-world outputs:

- **CEO** orchestrates the entire pipeline, reviews every agent's output with LLM-powered quality checks, and requests revisions when quality is insufficient (up to 2 rounds).
- **Product** generates a full product spec with personas, features, and user stories.
- **Engineer** builds an HTML landing page and ships it via GitHub (issue → branch → commit → PR).
- **Marketing** writes copy across channels and delivers it: a real cold email via SendGrid and a formatted Slack post via Block Kit.
- **QA** fetches the deployed HTML from the PR, reviews both the page and marketing copy against the product spec, and posts inline review comments directly on the GitHub PR.

Every external API call is wrapped with retry logic and exponential backoff. Messages between agents use Pydantic-validated schemas over atomic Redis operations to prevent race conditions.

---

## Features

| Feature | Description |
|:---|:---|
| **Multi-agent orchestration** | CEO decomposes the idea into tasks, dispatches to agents, reviews output, and triggers revision loops |
| **Product spec generation** | LLM-generated personas, features with priority levels, and user stories |
| **Landing page deployment** | Full responsive HTML page committed to GitHub with an issue, feature branch, and pull request |
| **Marketing copy suite** | Tagline, product description, cold email, and social posts (Twitter, LinkedIn, Instagram) |
| **Cold email delivery** | Real email sent to a test recipient via SendGrid |
| **Slack announcements** | Block Kit formatted launch post to a Slack channel |
| **QA code review** | LLM reviews HTML structure, accessibility, SEO, and copy consistency. Posts inline PR comments on GitHub |
| **Feedback loops** | CEO reviews agent output and requests up to 2 revision rounds if quality is insufficient |
| **Parallel execution** | Engineer and Marketing agents run simultaneously after Product completes |
| **Atomic messaging** | Redis pipeline transactions prevent race conditions in agent communication |
| **Retry with backoff** | All external API calls (LLM, GitHub, Slack, SendGrid) retry 3x with exponential backoff |

---

## Architecture

```
                              ┌──────────────┐
                              │   Startup    │
                              │    Idea      │
                              └──────┬───────┘
                                     │
                              ┌──────▼────────┐
                              │     CEO       │
                              │ (Orchestrator)│
                              └──────┬────────┘
                                     │ decompose
                              ┌──────▼───────┐
                              │   Product    │──── spec ────┐
                              │   Agent      │              │
                              └──────────────┘              │
                                                            │
                         ┌──────────────────────────────────┤
                         │                                  │
                  ┌──────▼───────┐                  ┌───────▼───────┐
                  │  Engineer    │                  │  Marketing    │
                  │  Agent       │                  │  Agent        │
                  ├──────────────┤                  ├───────────────┤
                  │ HTML page    │                  │ Cold email    │
                  │ GitHub PR    │                  │ Slack post    │
                  │ Issue        │                  │ Social copy   │
                  └──────┬───────┘                  └───────┬───────┘
                         │                                  │
                         └──────────┬───────────────────────┘
                                    │
                             ┌──────▼───────┐
                             │   QA Agent   │
                             ├──────────────┤
                             │ HTML review  │
                             │ Copy review  │
                             │ PR comments  │
                             └──────┬───────┘
                                    │
                             ┌──────▼───────┐
                             │  CEO Verdict │
                             │  pass/fail   │
                             └──────────────┘

         All agents communicate via Upstash Redis message bus
```

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| LLM | DeepSeek API (via OpenAI-compatible SDK) |
| Message Bus | Upstash Redis (serverless) |
| Code Hosting | GitHub REST API |
| Email | SendGrid |
| Notifications | Slack Block Kit API |
| Validation | Pydantic v2 + pydantic-settings |
| Runtime | Python 3.11+ |
| Package Manager | uv |

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for: [DeepSeek](https://platform.deepseek.com), [Upstash Redis](https://upstash.com), [GitHub](https://github.com/settings/tokens), [SendGrid](https://sendgrid.com), [Slack](https://api.slack.com/apps)
- A GitHub repository for landing pages (e.g., `YourUser/LaunchMind-LandingPages`) with at least one commit on `main`

---

## Getting Started

```bash
git clone https://github.com/EmamaNoor/LaunchMind.git
cd LaunchMind

# Install dependencies
uv sync

# Create .env and fill in your API credentials
```

Edit `.env` with your API credentials (see [Environment Variables](#environment-variables)), then run:

```bash
uv run python -m launchmind "Your startup idea here"
```

---

## Environment Variables

Create a `.env` file in the project root with the following:

| Variable | Required | Description |
|:---|:---|:---|
| `DEEPSEEK_API_KEY` | Yes | API key from [DeepSeek Platform](https://platform.deepseek.com) |
| `UPSTASH_REDIS_URL` | Yes | Redis connection URL from [Upstash Console](https://console.upstash.com) |
| `GITHUB_TOKEN` | Yes | GitHub personal access token with `repo` scope |
| `GITHUB_LANDING_REPO` | Yes | Target repo for landing pages (e.g., `EmamaNoor/LaunchMind-LandingPages`) |
| `VERCEL_TOKEN` | No | Vercel API token for automatic landing page deployment. If omitted, the Vercel deploy step is skipped |
| `SLACK_BOT_TOKEN` | Yes | Slack bot token (`xoxb-...`) from your [Slack App](https://api.slack.com/apps) |
| `SLACK_CHANNEL` | No | Slack channel to post to (default: `#launches`) |
| `SENDGRID_API_KEY` | Yes | API key from [SendGrid](https://app.sendgrid.com/settings/api_keys) |
| `SENDGRID_FROM_EMAIL` | Yes | Verified sender email in SendGrid |
| `TEST_EMAIL` | Yes | Recipient email for cold outreach testing |

---

## Project Structure

```
launchmind/
  agents/
    base.py              <- Agent ABC: listen(), send_message(), call_llm()
    ceo.py               <- Orchestrator: decompose, dispatch, review, revision loops
    product.py           <- Generates product spec (personas, features, user stories)
    engineer.py          <- Generates HTML landing page, creates GitHub issue + branch + PR
    marketing.py         <- Generates copy, sends cold email, posts to Slack
    qa.py                <- Reviews HTML + copy vs spec, posts inline PR review comments
  bus/
    models.py            <- Message schema and MessageType enum (Pydantic v2)
    transport.py         <- Redis-backed message bus with atomic receive via pipeline
  services/
    llm.py               <- DeepSeek API wrapper (OpenAI-compatible SDK)
    github.py            <- GitHub REST API: issues, branches, commits, PRs, reviews
    slack.py             <- Slack Block Kit message posting
    email.py             <- SendGrid cold email delivery
  config.py              <- Settings loaded from .env via pydantic-settings
  utils.py               <- Retry decorator with exponential backoff, ID generator
  logging_config.py      <- Structured logging setup
  app.py                 <- Entry point: wires all agents, runs ceo.run()
  __main__.py            <- Enables python -m launchmind
pyproject.toml           <- Dependencies and project metadata
```

---

## Usage

```bash
uv run python -m launchmind "A platform where local farmers sell surplus produce directly to restaurants the same morning it's harvested"
```

The system will:

1. **CEO** decomposes your idea into tasks for each agent
2. **Product** generates a full product spec. CEO reviews and may request revisions
3. **Engineer** builds an HTML landing page and opens a GitHub PR
4. **Marketing** generates copy, sends a cold email, and posts to Slack. Both run in parallel
5. **QA** fetches the HTML from the PR, reviews everything, and posts inline comments on GitHub
6. **CEO** evaluates the QA verdict. If it fails, revision requests are sent to the responsible agents

---

## Viewing the Landing Page

After each run, the Engineer automatically deploys the landing page to Vercel and commits the HTML to GitHub.

**Live Vercel URL (instant, no setup):**

The URL is printed at the end of every run:

```
Vercel: https://<product-name>.vercel.app
```

For example, a run for "StreetEats" produces:

```
https://streeteats.vercel.app
```

The URL is always `https://{product-name}.vercel.app`, matching the GitHub branch (`landing/{product-name}`) and committed file (`{product-name}/index.html`). If that alias is already claimed by another Vercel account, the run falls back to the unique deployment URL printed in the logs, which is also always live.

**GitHub source:**

The HTML is committed to your landing pages repo on a dedicated branch per product:

```
Branch:  landing/streeteats
File:    streeteats/index.html
Commit:  Live at: https://streeteats.vercel.app
```

A GitHub issue and pull request are also opened automatically for review.

---

## Contributing

1. Fork the repo and clone it locally
2. Install dependencies: `uv sync`
3. Copy `.env.example` to `.env` and fill in your API keys
4. Run the test suite: `uv run pytest`
5. Make your changes on a feature branch and open a pull request against `main`

Please keep PRs focused. One feature or fix per PR.

---

## License

MIT. See [LICENSE](LICENSE) for details.
