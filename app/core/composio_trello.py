from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from composio import Composio
from composio_claude_agent_sdk import ClaudeAgentSDKProvider
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from pydantic import BaseModel


# Initialize Composio + MCP server once per process.
composio = Composio(api_key="ak_18ecf6WKTWs7mkuW0kMV", provider=ClaudeAgentSDKProvider())

external_user_id = "pg-test-28f5fb2d-d0d2-450f-8b3b-1b652748a432"

session = composio.create(user_id=external_user_id)
tools = session.tools()
custom_server = create_sdk_mcp_server(name="composio", version="1.0.0", tools=tools)


class ActionTask(BaseModel):
    title: str
    reason: str
    subtasks: List[str]


class ActionTasksPayload(BaseModel):
    tasks: List[ActionTask]


def _parse_actions_payload(actions_result: Any) -> Optional[ActionTasksPayload]:
    """
    Normalize the raw actions_result into an ActionTasksPayload Pydantic model.

    Supports:
    - Direct dict with shape {"tasks": [...]}
    - Nested under keys like "result", "data", "content"
    - JSON string containing that structure
    """

    if actions_result is None:
        print("Composio Trello: actions_result is None")
        return None

    data: Any = actions_result

    # Peel common wrapper keys if present.
    for key in ("result", "data", "content"):
        if isinstance(data, dict) and key in data:
            data = data[key]

    # If it's a JSON string, parse it.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print("Composio Trello: error parsing actions_result as JSON string")
            return None

    if not isinstance(data, dict):
        print("Composio Trello: parsed actions_result is not a dict")
        return None

    try:
        payload = ActionTasksPayload.model_validate(data)
    except Exception as exc:  # pydantic validation error
        print(f"Composio Trello: failed to validate actions_result into model: {exc}")
        return None

    if not payload.tasks:
        print("Composio Trello: payload.tasks is empty")
        return None

    return payload


async def create_trello_task_from_actions_result(
    actions_result: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Take the first task (title + subtasks) from the actions_result payload and
    create a Trello task in the Project Chakravyuh board using Composio.

    Returns a small dict with debug metadata, or None if nothing was created.
    """

    #payload = _parse_actions_payload(actions_result)
    # if not payload:
    #     print("Composio Trello: no valid tasks payload extracted from actions_result")
    #     return None

    # first_task = payload.tasks[0]
    # title = first_task.title
    # subtasks = first_task.subtasks

    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant that uses Composio Trello tools to manage tasks.",
        permission_mode="bypassPermissions",
        mcp_servers={
            "composio": custom_server,
        },
    )

    query_text = (
        f"Create a new task list of tasks on Trello in the 'Project Chakravyuh' board for {actions_result} "
        # "Composio Trello tools. Use the following as the card title and checklist:\n\n"
        # f"Title: {title}\n"
        # "Checklist items:\n"
        # + "\n".join(f"- {s}" for s in subtasks)
    )

    #print("Composio Trello: creating task with title:", title)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(query_text)
        responses: List[Any] = []
        async for msg in client.receive_response():
            print("Composio Trello response message:", msg)
            responses.append(msg)

    return True

__all__ = ["create_trello_task_from_actions_result", "ActionTask", "ActionTasksPayload"]


