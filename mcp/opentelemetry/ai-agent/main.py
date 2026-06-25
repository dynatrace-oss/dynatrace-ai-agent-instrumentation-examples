import os
import random

from dynatrace import setup_tracing
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool


def setup_instrumentation():
    setup_tracing("mcp-agent-demo")


async def run_agent(message: str) -> str:
    mcp_client = MultiServerMCPClient(
        {
            "weather": {
                "url": "http://localhost:3000/mcp",
                "transport": "streamable_http",
            }
        }
    )

    @tool("get_city")
    def get_city() -> str:
        """Get the city."""
        cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Berlin", "London", "Tokyo"]
        city = random.choice(cities)
        print(f"Selected city: {city}")
        return city

    mcp_tools = await mcp_client.get_tools()
    tools = [get_city] + mcp_tools

    model = init_chat_model(
        model=os.environ.get('AZURE_OPENAI_DEPLOYMENT'),
        model_provider="azure_openai",
        api_version="2024-12-01-preview",
        azure_endpoint=os.environ.get('AZURE_OPENAI_ENDPOINT'),
        api_key=os.environ.get('AZURE_OPENAI_API_KEY'),
        temperature=0,
    )

    class WeatherResponse(BaseModel):
        response: str

    agent = create_react_agent(
        model=model,
        tools=tools,
        response_format=WeatherResponse,
        prompt="You are a helpful assistant that provides weather information for the retrieved city.",
    )

    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": message}]}
    )

    return response["structured_response"].response


if __name__ == "__main__":
    import asyncio
    setup_instrumentation()
    result = asyncio.run(run_agent("what is the weather?"))
    print(result)
