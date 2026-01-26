import json
from pathlib import Path
from typing import Any, Dict, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


CONTEXT_PATH = Path("url_context_output.json")


async def run_url_action_agent(
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Use the saved or provided URL context to propose concrete next actions.

    If `context` is not provided, this function will attempt to load it from
    `url_context_output.json` in the current working directory.
    """

    if context is None:
        if not CONTEXT_PATH.exists():
            raise FileNotFoundError(
                f"Expected context file {CONTEXT_PATH} not found. "
                "Run the URL context agent first to generate it."
            )

        raw_context = CONTEXT_PATH.read_text(encoding="utf-8")

        try:
            parsed_context: Dict[str, Any] = json.loads(raw_context)
        except json.JSONDecodeError:
            parsed_context = {"raw_context": raw_context}
    else:
        parsed_context = context

    prompt = f"""
You are a planning assistant.

You are given structured context summarizing the content of one or more URLs.
The context may include, for each URL: url, title, tags, content, and a short_summary.

Your job is to turn this context into a clear plan of **next actions** for the user:
- Identify 1–3 high-level tasks the user should do next.
- For each task, break it down into 2–5 concrete subtasks (small, actionable steps).
- Make the tasks specific and ordered so the user can execute them directly.
- If helpful, briefly reference which URL(s) each task is based on.

You MUST return your answer as a single valid JSON object (no markdown, no prose)
that matches this exact structure so it can be parsed into the following Pydantic
models on the backend:

ActionTask:
- "title": string, the task title
- "reason": string, a short explanation of why this task matters
- "subtasks": array of strings, each a concrete next step

ActionTasksPayload:
- "tasks": array of ActionTask objects

Example (shortened):
{{
  "tasks": [
    {{
      "title": "Evaluate Asteroid for your automation needs",
      "reason": "Determine if Asteroid's browser automation capabilities align with your workflow and ROI requirements",
      "subtasks": [
        "Identify 2-3 repetitive browser-based tasks",
        "Map out current time/cost spent on these processes"
      ]
    }}
  ]
}}

Here is the URL context:

{json.dumps(parsed_context, indent=2)}
"""

    final_payload: Dict[str, Any] | None = None

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
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
            print("AssistantMessage:")
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    print(block.text)
                elif hasattr(block, "name"):
                    print(f"Tool call: {block.name}")
        elif isinstance(message, ResultMessage):
            subtype = getattr(message, "subtype", None)
            if subtype is not None:
                print("Done:", subtype)
            else:
                print("Done: ResultMessage received")

            final_payload = {
                k: v for k, v in message.__dict__.items() if not k.startswith("_")
            }
            if final_payload:
                print("Final action plan data:")
                print(final_payload)

    return final_payload


__all__ = ["run_url_action_agent"]

