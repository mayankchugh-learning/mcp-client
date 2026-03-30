import asyncio

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

REMOTE_EXPENSE_MCP_URL = os.getenv(
    "REMOTE_EXPENSE_MCP_URL",
    "https://rapid-crimson-roundworm.fastmcp.app/mcp",
)
REMOTE_EXPENSE_MCP_TOKEN = os.getenv("REMOTE_EXPENSE_MCP_TOKEN")


def _env_truthy(name: str, default: str = "1") -> bool:
    raw = (os.getenv(name, default) or "").strip().strip('"').strip("'")
    return raw.lower() in ("1", "true", "yes", "on")


# Set MCP_ENABLE_MANIM=0 to skip manim during get_tools() (manim startup can hang or take minutes).
_ENABLE_MANIM = _env_truthy("MCP_ENABLE_MANIM", "1")


def build_server_connections() -> dict:
    connections = {
        "math-mcp-server": {
            "transport": "stdio",
            "command": "C:\\Users\\madfa\\.local\\bin\\uv.exe",
            "args": [
                "run",
                "--project",
                "C:\\githunb\\Claude\\math-mcp-server",
                "python",
                "C:\\githunb\\Claude\\math-mcp-server\\main.py",
            ],
        },
    }
    if _ENABLE_MANIM:
        connections["manim-server"] = {
            "transport": "stdio",
            "command": "C:\\ProgramData\\anaconda3\\python.exe",
            "args": [
                "C:\\githunb\\Claude\\ManimMCP\\manim-mcp-server\\src\\manim_server.py",
            ],
            "env": {
                "MANIM_EXECUTABLE": "C:\\Users\\madfa\\AppData\\Roaming\\Python\\Python313\\Scripts\\manim.exe",
            },
        }
    else:
        print(
            "Note: manim-server skipped (set MCP_ENABLE_MANIM=1 to enable). "
            "Startup is much faster without it.",
            flush=True,
        )
    if REMOTE_EXPENSE_MCP_TOKEN:
        connections["remote-expense-mcp"] = {
            "transport": "streamable_http",
            "url": REMOTE_EXPENSE_MCP_URL,
            "headers": {
                "Authorization": f"Bearer {REMOTE_EXPENSE_MCP_TOKEN}",
            },
        }
    else:
        print(
            "Note: remote-expense-mcp skipped (set REMOTE_EXPENSE_MCP_TOKEN in .env). "
            "Hosted FastMCP returns 401 without auth."
        )
    return connections


async def main():
    connections = build_server_connections()
    print(
        f"Loading MCP tools from {len(connections)} server(s) (this can take a while if manim is enabled)...",
        flush=True,
    )
    client = MultiServerMCPClient(
        connections,
        tool_name_prefix=True,
    )
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools. Calling model...\n", flush=True)

    anthropic_client = ChatAnthropic(
        model=ANTHROPIC_MODEL,
        api_key=ANTHROPIC_API_KEY,
    )
    llm_with_tools = anthropic_client.bind_tools(tools)
    tool_by_name = {t.name: t for t in tools}

    prompt = "Draw a animated circle using manim-server"
    if "manim" in prompt.lower() and not _ENABLE_MANIM:
        print(
            "Warning: prompt mentions Manim but MCP_ENABLE_MANIM is off — manim tools are not loaded.\n",
            flush=True,
        )

    # prompt = "Please list down all expenses & what is the total amount of expenses for the month of March 2026?"
    # prompt = "Please add a expense for a car rental in the amount of 1000 on 28Mar2026"
    # prompt = "What is the capital of France"

    messages: list[HumanMessage | AIMessage | ToolMessage] = [HumanMessage(content=prompt)]

    while True:
        ai_msg = await llm_with_tools.ainvoke(messages)
        messages.append(ai_msg)
        if not getattr(ai_msg, "tool_calls", None):
            print("--- Final answer ---")
            print(ai_msg.content)
            break
        for tc in ai_msg.tool_calls:
            tool = tool_by_name[tc["name"]]
            observation = await tool.ainvoke(tc["args"])
            if os.getenv("MCP_CLIENT_DEBUG"):
                print(f"[mcp] {tc['name']}({tc['args']!r}) -> {observation!r}")
            messages.append(
                ToolMessage(content=str(observation), tool_call_id=tc["id"])
            )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C) while running.", flush=True)
        raise SystemExit(130) from None