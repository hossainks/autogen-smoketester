import asyncio
import os
import subprocess

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams
from dotenv import load_dotenv
load_dotenv()

JIRA_MCP_IMAGE = "ghcr.io/sooperset/mcp-atlassian:latest"

def ensure_docker_image(image: str) -> None:
    """Pull the Docker image if not already cached locally."""
    print(f"Ensuring Docker image is available: {image}")
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        print(f"Pulling Docker image (this may take a minute): {image}")
        subprocess.run(["docker", "pull", image], check=True)
        print("Docker image pulled successfully.")
    else:
        print("Docker image already cached locally.")

async def main():
    print("Hello world")
    ensure_docker_image(JIRA_MCP_IMAGE)
    llm_client = OpenAIChatCompletionClient(model="gpt-5-mini")

    jira_params = StdioServerParams(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", "JIRA_URL",
            "-e", "JIRA_USERNAME",
            "-e", "JIRA_API_TOKEN",
            "-e", "JIRA_PROJECTS_FILTER",
            JIRA_MCP_IMAGE,
        ],
        env={  # type: ignore[arg-type]
            "JIRA_URL": os.environ["JIRA_URL"],
            "JIRA_USERNAME": os.environ["JIRA_USERNAME"],
            "JIRA_API_TOKEN": os.environ["JIRA_API_TOKEN"],
            "JIRA_PROJECTS_FILTER": os.environ["JIRA_PROJECTS_FILTER"],
        },
        read_timeout_seconds=60,  # Allow up to 60s for Docker container startup + MCP init
    )
    jira_workbench = McpWorkbench(server_params=jira_params)

    playwright_params = StdioServerParams(
        command="npx",
        args=["@playwright/mcp@latest"],
        read_timeout_seconds=60,  # Allow up to 60s for npx download + Playwright MCP startup
    )
    playwright_workbench = McpWorkbench(server_params=playwright_params)


    async with jira_workbench as jira_wb, playwright_workbench as pw_eb:
        bug_analyst = AssistantAgent(
            name="BugAnalyst",
            model_client=llm_client,
            system_message=("""
                You are a Bug Analyst specializing in Jira defect analysis. Your task is as follows:
                    Goal -- Your role is to analyze defects and create comprehensive test scenarios.

                    IMPORTANT: You MUST use the jira_search tool to fetch real bugs. Do NOT make up, assume,
                    or hallucinate any bugs. If the tool returns zero results, try a broader JQL query before giving up.

                    MANDATORY FIRST STEP — Call jira_search with this JQL:
                        project = SCRUM AND issuetype = Bug ORDER BY created DESC
                    Retrieve the most recent 5 bugs. Fields to request: summary, status, description.

                    2. Carefully read the REAL bug descriptions returned by the tool and identify recurring issues or common patterns.
                    3. Based on these patterns, design a detailed user flow that exercises the core features of the application
                       and can serve as a robust smoke test scenario using REAL URLs like http://localhost:3000/practise/

                    Be very specific in your smoke test design:
                    - Provide clear, step-by-step manual testing instructions.
                    - Include exact URLs or page routes to visit.
                    - Describe user actions (clicks, form inputs, submissions).
                    - Clearly state the expected outcomes or validations for each step.

                    If jira_search returns zero bugs, try re-querying with a wider JQL (e.g. remove the issuetype filter)
                    and note clearly what was found.

                    When your analysis and scenario preparation is complete:
                    - Clearly output the final smoke testing steps.
                    - Finally, write: **'HANDOFF TO AUTOMATION'** to signal completion of your analysis.
                """),
            workbench=jira_wb,
        )
        automation_analyst = AssistantAgent(
            name="AutomationAgent",
            model_client=llm_client,
            system_message=("""
                You are a Playwright automation expert. Take the user flow from BugAnalyst
                and execute it step by step using Playwright MCP tools.

                === CRITICAL TOOL USAGE RULES ===

                1. ALWAYS take a browser_snapshot FIRST after navigating to understand the page structure.
                   Use the snapshot to find the REAL element refs/selectors before interacting.

                2. browser_wait_for accepts VISIBLE PAGE TEXT only - NOT CSS selectors.
                   CORRECT:   {"text": "Code applied ..!", "time": 10}
                   WRONG:     {"text": "input[type='text']", "time": 10}  ← NEVER do this

                3. NEVER run multiple steps in parallel if they depend on each other.
                   Always wait for one step to complete before starting the next.

                4. To interact with a hidden input (e.g. React Select dropdowns):
                   - First click the visible parent/container element
                   - Then use browser_type to type into it

                5. Use browser_snapshot to get current page state when selectors fail.
                   The snapshot shows real aria refs like [ref=e123] — use those.

                6. For the search box on GreenKart:
                   - Click the search input area first (it's a React Select component)
                   - Then use browser_type to type the product name

                7. For the coupon flow: first add an item to cart using the
                   "Add to Cart" button next to a product, THEN click the cart icon,
                   THEN proceed to checkout to reach the coupon field.

                8. Use browser_wait_for with actual SUCCESS or ERROR text from the page
                   (e.g. "Code applied ..!" or "Invalid code") after async actions.

                9. Take screenshots at key validation points.

                10. Only say 'TESTING COMPLETE' after ALL steps are fully executed.
            """),
            workbench=pw_eb,
        )

        team = RoundRobinGroupChat(participants=[bug_analyst, automation_analyst],termination_condition=TextMentionTermination('TESTING COMPLETE'))

        await Console(team.run_stream(task=(""" 
               BugAnalyst:\n
                1. Search for recent bugs in SCRUM project\n
                2. Then design a stable user flow that can be used as a smoke test.\n
                3. Use REAL URLs like http://localhost:3000/practise/\n

                AutomationAgent:\n
                Once ready, automate this flow using Playwright MCP and execute it."
                """ )
                                      ))
    await llm_client.close()

asyncio.run(main())
