import asyncio
from composio import Composio
from composio_claude_agent_sdk import ClaudeAgentSDKProvider
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server

# Initialize Composio
composio = Composio(
    api_key="ak_18ecf6WKTWs7mkuW0kMV",
    provider=ClaudeAgentSDKProvider()
)

external_user_id = "pg-test-28f5fb2d-d0d2-450f-8b3b-1b652748a432"

# Create a tool router session
session = composio.create(
    user_id=external_user_id,
)

# Get tools from the session (native)
tools = session.tools()
custom_server = create_sdk_mcp_server(name="composio", version="1.0.0", tools=tools)
print(custom_server)
# Query Claude with MCP tools
async def main():
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant",
        permission_mode="bypassPermissions",
        mcp_servers={
            "composio": custom_server,
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(f"Create a new task 'explore mem agent reasearch conference' on trello in Project Chakravyuh board")
        # Extract and print response
        async for msg in client.receive_response():
            print(msg)

asyncio.run(main())