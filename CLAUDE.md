# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the smoketester

```powershell
# Activate the virtual environment first
.venv\Scripts\Activate.ps1

# Run the smoketester
python smoketester.py
```

## Environment setup

Copy the required variables into a `.env` file (gitignored) before running:

```
JIRA_URL=https://your-org.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=your_token
JIRA_PROJECTS_FILTER=SCRUM
OPENAI_API_KEY=your_openai_key
```

## Dependencies

No `requirements.txt` exists — dependencies are tracked only via `.venv`. Key packages:
- `autogen-agentchat` / `autogen-ext` 0.7.5 — multi-agent orchestration
- `openai` 2.33.0 — LLM client (gpt-5-mini)
- `mcp` 1.27.0 — MCP tool protocol
- `python-dotenv` — `.env` loading

To install from scratch:
```powershell
pip install autogen-agentchat autogen-ext[openai,mcp] python-dotenv
```

## External dependencies at runtime

- **Docker** — must be running; pulls `ghcr.io/sooperset/mcp-atlassian:latest` on first run for the Jira MCP server
- **Node.js / npx** — used to launch `@playwright/mcp@latest` for browser automation

## Architecture

`smoketester.py` is a single-file agentic pipeline built on AutoGen:

1. **`BugAnalyst` agent** — queries Jira via the `mcp-atlassian` Docker MCP server, finds recent bugs in the configured project, and produces step-by-step smoke test instructions. It signals handoff with the token `HANDOFF TO AUTOMATION`.

2. **`AutomationAgent` agent** — receives the smoke test steps and executes them in a real browser via the Playwright MCP server (`@playwright/mcp`). It signals completion with `TESTING COMPLETE`.

3. **`RoundRobinGroupChat`** — orchestrates the two agents in turn; the conversation terminates when `TESTING COMPLETE` appears.

Both agents share a single `OpenAIChatCompletionClient` (gpt-5-mini). The Jira and Playwright MCP servers are launched as child processes via `McpWorkbench` and torn down via `async with` context managers.

The target application under test is a locally running instance at `http://localhost:3000/practise/` (GreenKart demo app).
