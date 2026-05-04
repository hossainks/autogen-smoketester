# Autogen Smoketester

An autonomous QA pipeline that reads real Jira bugs, designs smoke tests from them, and executes those tests in a live browser — all without human intervention.

Built on Microsoft AutoGen's multi-agent framework with MCP (Model Context Protocol) tool servers for Jira and Playwright.

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                     RoundRobinGroupChat                         │
│                                                                 │
│  ┌──────────────────┐   HANDOFF TO      ┌────────────────────┐ │
│  │   BugAnalyst     │  ──AUTOMATION──▶  │  AutomationAgent   │ │
│  │                  │                   │                    │ │
│  │  Jira MCP        │                   │  Playwright MCP    │ │
│  │  (Docker)        │                   │  (npx)             │ │
│  └──────────────────┘                   └────────────────────┘ │
│                                               │                 │
│                                         TESTING COMPLETE        │
│                                         (terminates loop)       │
└─────────────────────────────────────────────────────────────────┘
```

**Step 1 — Bug Analysis (`BugAnalyst` agent)**
Connects to Jira via a Dockerized MCP server, queries the last 5 bugs in the project using JQL, identifies recurring patterns, and produces detailed step-by-step smoke test instructions with real URLs and expected outcomes.

**Step 2 — Browser Automation (`AutomationAgent` agent)**
Receives the test plan and drives a real browser using the Playwright MCP server. It navigates pages, interacts with elements using live aria snapshots (not brittle CSS selectors), waits for real on-screen text, and captures screenshots at validation points.

**Step 3 — Termination**
The pipeline ends when `AutomationAgent` outputs `TESTING COMPLETE`, enforced by AutoGen's `TextMentionTermination` condition.

---

## Tech stack

| Layer | Technology |
|---|---|
| Multi-agent orchestration | [Microsoft AutoGen](https://github.com/microsoft/autogen) 0.7.5 |
| LLM backbone | OpenAI `gpt-5-mini` |
| Tool protocol | [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) |
| Jira integration | [`mcp-atlassian`](https://github.com/sooperset/mcp-atlassian) via Docker |
| Browser automation | [`@playwright/mcp`](https://github.com/microsoft/playwright-mcp) via npx |
| Config | `python-dotenv` |

---

## Prerequisites

- Python 3.11+
- Docker Desktop (running)
- Node.js + npx
- A Jira Cloud account with an API token
- An OpenAI API key
- The target web application running locally at `http://localhost:3000`

---

## Setup

```bash
# 1. Clone and create a virtual environment
git clone <repo-url>
cd autogen-smoketester
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install autogen-agentchat "autogen-ext[openai,mcp]" python-dotenv

# 3. Configure environment
cp .env.example .env          # then fill in your values
```

**.env**
```
OPENAI_API_KEY=sk-...
JIRA_URL=https://your-org.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=your_atlassian_api_token
JIRA_PROJECTS_FILTER=SCRUM
```

---

## Run

> **Before running**, make sure your target web application is running at `http://localhost:3000`.
> The smoke tests will navigate to `http://localhost:3000/practise/` by default.

```bash
python smoketester.py
```

On first run, Docker will pull the `mcp-atlassian` image (~1 min). Subsequent runs use the cached image.

The pipeline will stream both agents' reasoning and actions to the console in real time via AutoGen's `Console` UI.

---

## Design decisions

**Why MCP tool servers instead of direct API clients?**
MCP decouples tool capability from agent logic. Either tool server can be swapped (e.g. replace `mcp-atlassian` with a GitHub Issues MCP) without touching agent code.

**Why `RoundRobinGroupChat` with a text termination condition?**
It keeps orchestration stateless and declarative. The `TESTING COMPLETE` sentinel is part of the agent's output contract, making the pipeline self-terminating without polling or external state management.

**Why aria snapshots over CSS selectors in Playwright?**
Modern web frameworks (React, Vue) generate unstable class names. Aria ref snapshots (`[ref=e123]`) reflect the live accessibility tree and survive re-renders, making automation more resilient against UI changes — a pattern validated by real failures in the target app's bug history.

---

## Project structure

```
autogen-smoketester/
├── smoketester.py      # entire pipeline — agent definitions, MCP config, orchestration
├── .env.example        # template for required environment variables
├── .env                # secrets (gitignored)
├── .gitignore          # excludes .env from version control
└── .playwright-mcp/    # Playwright MCP runtime logs and page snapshots
```
