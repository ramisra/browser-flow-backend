import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


CONTEXT_PATH = Path("url_context_output.json")


async def main() -> None:
    """
    Use the saved URL context from url_context_agent.py to propose concrete next actions.

    Responsibilities of this agent:
    1. Load the structured context previously saved by url_context_agent.py.
    2. Ask Claude to synthesize this into a set of tasks and subtasks (next action items).
    3. Stream progress and final task plan to the console.
    """

    if not CONTEXT_PATH.exists():
        raise FileNotFoundError(
            f"Expected context file {CONTEXT_PATH} not found. "
            "Run url_context_agent.py first to generate it."
        )

    raw_context = CONTEXT_PATH.read_text(encoding="utf-8")

    # We don't assume a strict schema here; treat the saved JSON as opaque context.
    try:
        parsed_context: Dict[str, Any] = json.loads(raw_context)
    except json.JSONDecodeError:
        # Fall back to treating the file as plain text if it's somehow not valid JSON.
        parsed_context = {"raw_context": raw_context}

    prompt = f"""
You are a planning assistant.

You are given structured context summarizing the content of one or more URLs.
The context may include, for each URL: url, title, tags, content, and a short_summary.

Your job is to turn this context into a clear plan of **next actions** for the user:
- Identify 1–3 high-level tasks the user should do next.
- For each task, break it down into 2–5 concrete subtasks (small, actionable steps).
- Make the tasks specific and ordered so the user can execute them directly.
- If helpful, briefly reference which URL(s) each task is based on.

Return your answer as a concise JSON object with:
- "tasks": a list of objects, each with:
  - "title": string, the task title
  - "reason": short string explaining why this task matters
  - "subtasks": list of short strings, each a concrete next step

Here is the URL context:

{json.dumps(parsed_context, indent=2)}
"""

    # Agentic loop: stream messages as Claude works
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            # No need for web tools here; we only operate on existing context.
            allowed_tools=["Read", "Edit", "Glob"],
            permission_mode="acceptEdits",
            system_prompt=(
                "You are a senior product manager and research engineer. "
                "Given context, you design clear, prioritized task lists with actionable subtasks."
            ),
        ),
    ):
        print(f"Message: {message}")
        if isinstance(message, AssistantMessage):
            # Print human-readable output as it streams
            print("AssistantMessage:")
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    print(block.text)
                elif hasattr(block, "name"):
                    # Tool call information
                    print(f"Tool call: {block.name}")
        elif isinstance(message, ResultMessage):
            # Final structured result from the agent
            subtype = getattr(message, "subtype", None)
            if subtype is not None:
                print("Done:", subtype)
            else:
                print("Done: ResultMessage received")

            printable = {
                k: v
                for k, v in message.__dict__.items()
                if not k.startswith("_")
            }
            if printable:
                print("Final action plan data:")
                print(printable)


if __name__ == "__main__":
    asyncio.run(main())