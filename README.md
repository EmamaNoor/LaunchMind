<div align="center">

# LaunchMind

**Multi-agent AI system that turns a startup idea into real-world outputs in under 2 minutes**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFF?logo=openai&logoColor=white)](https://platform.deepseek.com)
[![Redis](https://img.shields.io/badge/Upstash-Redis-DC382D?logo=redis&logoColor=white)](https://upstash.com)

Give it a startup idea. Five AI agents collaborate to produce a product spec, a deployed landing page with a GitHub PR, cold outreach emails, Slack announcements and a QA code review. All autonomously.

[Live Demo](https://launch-mind.vercel.app)

</div>

---

## Overview

LaunchMind is a custom multi-agent system built from scratch without CrewAI or LangGraph. Five specialized AI agents communicate through a Redis message bus, each producing tangible real-world outputs:

- **CEO** orchestrates the pipeline, reviews every agent's output with LLM-powered quality checks and requests up to 2 revision rounds when quality is insufficient.
- **Product** generates a full product spec with personas, prioritized features and user stories.
- **Engineer** builds a responsive HTML landing page and ships it via GitHub (issue, branch, commit, PR, Vercel deploy).
- **Marketing** writes copy across channels and delivers it through a cold email via SendGrid and a formatted Slack announcement via Block Kit.
- **QA** fetches the deployed HTML from the PR, reviews the page and marketing copy against the product spec and posts inline review comments directly on the GitHub PR.

Every external API call is wrapped with retry logic and exponential backoff. Messages between agents use Pydantic-validated schemas over atomic Redis operations to prevent race conditions.

---

## Features

| Feature | Description |
|:---|:---|
| **Multi-agent orchestration** | CEO decomposes the idea into tasks, dispatches to agents, reviews output and triggers revision loops |
| **Product spec generation** | LLM-generated personas, features with priority levels and user stories |
| **Landing page deployment** | Responsive HTML page committed to GitHub with issue, branch, PR and live Vercel deploy |
| **Marketing copy suite** | Tagline, description, cold email and social posts (Twitter, LinkedIn, Instagram) |
| **Cold email delivery** | Real email sent via SendGrid |
| **Slack announcements** | Block Kit formatted launch post to a Slack channel |
| **QA code review** | LLM reviews HTML structure, accessibility, SEO and copy consistency with inline PR comments |
| **Feedback loops** | CEO reviews output and requests up to 2 revision rounds if quality is insufficient |
| **Parallel execution** | Engineer and Marketing agents run simultaneously after Product completes |
| **Web interface** | FastAPI backend with fire-and-forget pattern + frontend with real-time progress tracking |
| **Atomic messaging** | Redis pipeline transactions prevent race conditions in agent communication |
| **Retry with backoff** | All external API calls retry 3x with exponential backoff |

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
             ├──────────────┤                  ├───────────────┤
             │ HTML page    │                  │ Cold email    │
             │ GitHub PR    │                  │ Slack post    │
             │ Vercel deploy│                  │ Social copy   │
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
| LLM | DeepSeek API (OpenAI-compatible SDK) |
| Message Bus | Upstash Redis (serverless) |
| API Server | FastAPI + Uvicorn |
| Code Hosting | GitHub REST API |
| Landing Pages | Vercel (auto-deploy) |
| Email | SendGrid |
| Notifications | Slack Block Kit |
| Validation | Pydantic v2 |
| Runtime | Python 3.11+ / uv |

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for: [DeepSeek](https://platform.deepseek.com), [Upstash Redis](https://upstash.com), [GitHub](https://github.com/settings/tokens), [SendGrid](https://sendgrid.com), [Slack](https://api.slack.com/apps)
- A GitHub repository for landing pages (e.g., `YourUser/LaunchMind-LandingPages`) with at least one commit on `main`

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
