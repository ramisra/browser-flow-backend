import asyncio
import json
from typing import List, Any, Dict

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from urls import urls


async def main() -> None:
    """
    Use Claude + the web fetch tool to:
    1. Fetch the content of each URL from urls.py.
    2. Classify / tag the content (e.g. research paper, docs, blog, marketing, etc.).
    3. Stream progress to the console.
    4. Persist the final structured result to url_context_output.json for downstream use
       by calling the Bash tool (not by writing the file directly in Python).
    """

    # Turn the list of URLs into a bullet list for the prompt.
    url_list: List[str] = urls
    urls_markdown = "\n".join(f"- {u}" for u in url_list)

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

    final_payload: Dict[str, Any] | None = None

    # Agentic loop: stream messages as Claude works
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            # Allow the agent to call the web fetch tool plus general tools if needed.
            allowed_tools=["WebFetch", "Read", "Edit", "Glob", "Bash"],
            permission_mode="acceptEdits",
            system_prompt=(
                "You are a senior research assistant. "
                "Always use the web fetch tool to open URLs instead of guessing content. "
                "Be accurate and concise when assigning tags. "
                "When you have your final JSON result, use the Bash tool to write it "
                "to a file called url_context_output.json in the current working directory."
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

            # Some SDK versions don't expose a .content attribute on ResultMessage.
            # Safely capture whatever data is available without assuming a specific shape.
            final_payload = {
                k: v
                for k, v in message.__dict__.items()
                if not k.startswith("_")
            }
            if final_payload:
                print("Final result data:")
                print(final_payload)


if __name__ == "__main__":
    asyncio.run(main())