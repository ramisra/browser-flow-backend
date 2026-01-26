import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


async def run_url_context_agent(
    urls: Optional[List[str]] = None, context: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Use Claude to process context or URLs:
    1. If context is provided, use it directly (no web fetching needed).
    2. If context is not provided, fetch the content of each URL from the provided list.
    3. Classify / tag the content (e.g. research paper, docs, blog, marketing, etc.).
    4. Stream progress (stdout) for observability.
    5. Persist the final structured result to url_context_output.json for downstream use
       by calling the Bash tool (not by writing the file directly in Python).
    """

    # Priority: context takes precedence over URLs
    if context:
        # Use context directly, no web fetching needed
        prompt = f"""
You are a research assistant.

You are given context content. Your task is to:
- Analyze the provided context content.
- Extract the main textual content.
- Assign 2–5 descriptive tags that summarize what the content is about.
  Examples of tags: "research paper", "ICLR paper", "documentation", "API reference",
  "blog post", "product marketing", "landing page", "tutorial", "news", "other".
- Return the result as a JSON object with:
  - url (if available from context, otherwise "provided_context")
  - title (if available)
  - tags (list of strings)
  - content (the main textual content)
  - short_summary (2–3 sentences).

After you have built the JSON result:
- Call the Bash tool ONCE with a command that writes this JSON to a file named
  `url_context_output.json` in the current working directory.
- Overwrite any existing file of that name.
- Do not ask the user for confirmation; just write the file.

Here is the context:

{context}
"""

        allowed_tools = ["Read", "Edit", "Glob", "Bash"]
        system_prompt = (
            "You are a senior research assistant. "
            "You have been provided with context directly - do not use web fetch tools. "
            "Be accurate and concise when assigning tags. "
            "When you have your final JSON result, use the Bash tool to write it "
            "to a file called url_context_output.json in the current working directory."
        )
    elif urls:
        # Fall back to URL-based fetching
        urls_markdown = "\n".join(f"- {u}" for u in urls)

        prompt = f"""
You are a research assistant.

You are given a list of URLs. For each URL:
- Use the web fetch tool to open and read the page.
- Extract the main textual content (ignore navigation, boilerplate, and cookie banners).
- Assign 2–5 descriptive tags that summarize what the page is about.
  Examples of tags: "research paper", "ICLR paper", "documentation", "API reference",
  "blog post", "product marketing", "landing page", "tutorial", "news", "other".
- Return the result as a small JSON object for each URL with:
  - url
  - title (if available)
  - tags (list of strings)
  - content (the main textual content of the page)
  - short_summary (2–3 sentences).

After you have built the full JSON result for all URLs:
- Call the Bash tool ONCE with a command that writes this JSON to a file named
  `url_context_output.json` in the current working directory.
- Overwrite any existing file of that name.
- Do not ask the user for confirmation; just write the file.

Here are the URLs:

{urls_markdown}
"""

        allowed_tools = ["WebFetch", "Read", "Edit", "Glob", "Bash"]
        system_prompt = (
            "You are a senior research assistant. "
            "Always use the web fetch tool to open URLs instead of guessing content. "
            "Be accurate and concise when assigning tags. "
            "When you have your final JSON result, use the Bash tool to write it "
            "to a file called url_context_output.json in the current working directory."
        )
    else:
        raise ValueError("Either urls or context must be provided")

    final_payload: Dict[str, Any] | None = None
    context_output_path = Path("url_context_output.json")

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits",
            system_prompt=system_prompt,
        ),
    ):
        # Keep stdout logging behavior for debugging/observability.
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
                print("Final result data:")
                print(final_payload)

    # Read the JSON file that was created by the agent
    parsed_result: Optional[Dict[str, Any]] = None
    if context_output_path.exists():
        try:
            with open(context_output_path, "r", encoding="utf-8") as f:
                file_content = f.read().strip()
                if file_content:
                    parsed_result = json.loads(file_content)
                    print(f"Successfully parsed context from {context_output_path}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from {context_output_path}: {e}")
        except Exception as e:
            print(f"Error reading {context_output_path}: {e}")
    else:
        print(f"Warning: {context_output_path} not found after agent execution")

    # Return the parsed JSON result if available, otherwise return the final_payload
    # If parsed_result is a list (multiple URLs), return as-is
    # If it's a single object, wrap it in a list for consistency
    if parsed_result:
        # Handle both single object and list of objects
        if isinstance(parsed_result, list):
            return {"contexts": parsed_result}
        else:
            return {"contexts": [parsed_result]}

    # Fallback: return final_payload if JSON file wasn't created/parsed
    return final_payload


__all__ = ["run_url_context_agent"]

