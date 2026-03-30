import asyncio

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


SERVERS = {
    "math-mcp-server": {
        "transport": "stdio",
        "command": "C:\\Users\\madfa\\.local\\bin\\uv.exe",
        "args": [
            "run",
            "--project",
            "C:\\githunb\\Claude\\math-mcp-server",
            "python",
            "C:\\githunb\\Claude\\math-mcp-server\\main.py"
        ]
    }
}



async def main():
    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()
    #print(tools)
    print("")

    anthropic_client = ChatAnthropic(
        model=ANTHROPIC_MODEL,
        api_key=ANTHROPIC_API_KEY,
    )
    llm_with_tools = anthropic_client.bind_tools(tools)
    tool_by_name = {t.name: t for t in tools}

    prompt = "What is the remainder of 565464 and 55?"
    # prompt = "What is the capital of France"

    reponse = await llm_with_tools.ainvoke(prompt)
    # print(result)
    print("--------------------------------")

    if not getattr(reponse, "tool_calls", None):
            print("\n --- LLM response ---", "\n", reponse.content)
            return
    # print("Response: ", result.tool_calls[0]["name"])

    selected_tools = reponse.tool_calls[0]["name"]
    #print("Selected tool: ", selected_tools)
    selected_tool_id = reponse.tool_calls[0]["id"]

    selected_tools_args = reponse.tool_calls[0]["args"]
    #print("Selected tool args: ", selected_tools_args)

    tool_result = await tool_by_name[selected_tools].ainvoke(selected_tools_args)
    #print("Tool response: ", tool_response)

    tool_message = ToolMessage(content=str(tool_result), tool_call_id=selected_tool_id)

    final_response = await llm_with_tools.ainvoke([reponse, tool_message])
    print("Final response: ", final_response)
    """ messages: list[HumanMessage | AIMessage | ToolMessage] = [HumanMessage(content=prompt)]

    for _ in range(8):
        ai_msg = await llm_with_tools.ainvoke(messages)
        messages.append(ai_msg)
        if not getattr(ai_msg, "tool_calls", None):
            print("--- Final answer ---")
            print(ai_msg.content)
            break
        for tc in ai_msg.tool_calls:
            tool = tool_by_name[tc["name"]]
            observation = await tool.ainvoke(tc["args"])
            messages.append(
                ToolMessage(content=str(observation), tool_call_id=tc["id"])
            )
    else:
        print("Stopped: max tool rounds reached; last message:")
        print(messages[-1].content)
        """

if __name__ == "__main__":
    asyncio.run(main())