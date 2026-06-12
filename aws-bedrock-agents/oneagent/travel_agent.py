import os
from typing import Annotated
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from ddgs import DDGS



os.environ["LANGSMITH_OTEL_ENABLED"] = "true"

@tool("web_search")
def web_search(query: str) -> str:
    """Search the web for current information about destinations, attractions, events, and general topics."""
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=5)
        
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )
        
        return "\n".join(formatted_results) if formatted_results else "No results found."
        
    except Exception as e:
        return f"Search error: {str(e)}"

def get_llm():
    model_id = os.getenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-3-7-sonnet-20250219-v1:0")
    
    try:
        llm = init_chat_model(
            model_id,
            model_provider="bedrock_converse",
            temperature=0.0,
            max_tokens=512,
        )
        return llm
    except Exception as e:
        raise

llm = get_llm()
tools = [web_search]
llm_with_tools = llm.bind_tools(tools)

class State(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: State):
    try:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}
    except Exception as e:
        from langchain_core.messages import AIMessage
        error_response = AIMessage(content=f"I apologize, but I encountered an error: {str(e)}")
        return {"messages": [error_response]}

graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

graph = graph_builder.compile()
graph_configured = True

def agent_invocation(payload: str, session_id: str = "default_session"):
    try:
        config = {"configurable": {"session_id": session_id}}
        tmp_msg = {"messages": [{"role": "user", "content": payload}]}
        
        tmp_output = graph.invoke(tmp_msg, config=config)
        
        result = tmp_output['messages'][-1].content
        
        return {
            "result": result,
            "status": "success",
            "session_id": session_id
        }
        
    except Exception as e:
        return {
            "result": "I apologize, but I encountered an error processing your request. Please try again.",
            "status": "error",
            "error": str(e),
            "session_id": session_id
        }

def run_agent_with_task(task_description: str, session_id: str = "task_session"):
    enhanced_prompt = f"""
    You are an experienced research agent with access to real-time web information.
    Your task is: {task_description}
    
    Please provide a comprehensive response with:
    1. Current and accurate information (use web search when needed)
    2. Practical details and recommendations
    3. Clear structure and organization
    4. Relevant sources when applicable
    
    Task: {task_description}
    """
    
    return agent_invocation(enhanced_prompt, session_id)
