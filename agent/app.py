import asyncio
import json
import os
from dotenv import load_dotenv

from agent.clients.custom_mcp_client import CustomMCPClient
from agent.clients.mcp_client import MCPClient
from agent.clients.dial_client import DialClient
from agent.models.message import Message, Role

load_dotenv()

async def _collect_tools(
        client: MCPClient | CustomMCPClient,
        tools: list[dict],
        tool_name_client_map: dict[str, MCPClient | CustomMCPClient]
):
    for tool in await client.get_tools():
        tools.append(tool)
        tool_name_client_map[tool.get('function', {}).get('name')] = client
        print(f"{json.dumps(tool, indent=2)}")

async def main():
    #TODO:
    # 1. Take a look what applies DialClient
    # 2. Create empty list where you save tools from MCP Servers later
    tools: list(dict) = []
    # 3. Create empty dict where where key is str (tool name) and value is instance of MCPClient or CustomMCPClient
    tool_name_client_map: dict[str, MCPClient | CustomMCPClient] = {}
    # 4. Create UMS MCPClient, url is `http://localhost:8006/mcp` (use static method create and don't forget that its async)
    ums_mcp_client: MCPClient | None = await MCPClient.create(mcp_server_url="http://localhost:8006/mcp")
    # 5. Collect tools and dict [tool name, mcp client]
    await _collect_tools(
        client=ums_mcp_client,
        tools=tools,
        tool_name_client_map=tool_name_client_map)
    # 6. Do steps 4 and 5 for `https://remote.mcpservers.org/fetch/mcp`
    fetch_mcp_client: CustomMCPClient | None = await CustomMCPClient.create(
        "https://remote.mcpservers.org/fetch/mcp",
        verify_ssl=False
    )
    await _collect_tools(
        client=fetch_mcp_client,
        tools=tools,
        tool_name_client_map=tool_name_client_map)
    # 7. Create DialClient, endpoint is `https://ai-proxy.lab.epam.com`
    dial_client = DialClient(
        api_key=os.getenv("DIAL_API_KEY"),
        endpoint="https://ai-proxy.lab.epam.com",
        tools=tools,
        tool_name_client_map=tool_name_client_map
    )
    # 8. Create array with Messages and add there System message with simple instructions for LLM that it should help to handle user request
    messages: list[Message] = [
        Message(role=Role.SYSTEM,
                content="You are an advanced AI agent. Your goal is to help user with his questions.")
    ]
    # 9. Create simple console chat (as we done in previous tasks)
    try:
        print("Type your query or 'exit' to exit.")
        while True:
            user_input = input("\n> ").strip()
            if user_input.lower() == 'exit':
                break

            messages.append(
                Message(
                    role=Role.USER,
                    content=user_input
                )
            )

            ai_message: Message = await dial_client.get_completion(messages)
            messages.append(ai_message)
    finally:
        if ums_mcp_client:
            await ums_mcp_client.close()
        if fetch_mcp_client:
            await fetch_mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())


# Check if Arkadiy Dobkin present as a user, if not then search info about him in the web and add him
