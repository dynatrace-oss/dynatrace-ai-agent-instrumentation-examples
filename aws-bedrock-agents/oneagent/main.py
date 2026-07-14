import os
from typing import Annotated
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from bedrock_agentcore import BedrockAgentCoreApp

import oneagent
oneagent.initialize()

agentcore = BedrockAgentCoreApp()


@tool("web_search")
def web_search(query: str) -> str:
    """Search the web for current information about destinations, attractions, events, and general topics."""
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=3)
        return "\n".join(
            f"{i}. {r.get('title', '')}\n   {r.get('body', '')}"
            for i, r in enumerate(results, 1)
        ) or "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"


_llm_with_tools = None


def _get_llm_with_tools():
    global _llm_with_tools
    if _llm_with_tools is None:
        llm = ChatBedrockConverse(
            model=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            temperature=0.0,
            max_tokens=512,
        )
        _llm_with_tools = llm.bind_tools([web_search])
    return _llm_with_tools


class State(TypedDict):
    messages: Annotated[list, add_messages]


def chatbot(state: State):
    return {"messages": [_get_llm_with_tools().invoke(state["messages"])]}


graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=[web_search]))
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile()


def run_agent(task: str) -> str:
    output = graph.invoke({"messages": [{"role": "user", "content": task}]})
    return output["messages"][-1].content


@agentcore.entrypoint
async def invoke(payload):
    task = payload.get("prompt", "")
    import asyncio
    result = await asyncio.to_thread(run_agent, task)
    yield result


if __name__ == "__main__":
    agentcore.run(port=int(os.getenv("PORT", "8000")))
