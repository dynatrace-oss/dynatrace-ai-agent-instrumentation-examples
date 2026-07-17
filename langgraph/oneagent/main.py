import os
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, StateGraph


def setup_instrumentation() -> None:
    import oneagent
    oneagent.initialize()


class HaikuState(TypedDict):
    topic: str
    haiku: str


def _build_graph():
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("MODEL", "genai-demo"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-07-01-preview"),
    )

    def write_haiku_node(state: HaikuState) -> HaikuState:
        response = llm.invoke(
            [
                SystemMessage(
                    content="You are a skilled poet specializing in haiku. "
                    "Reply with a haiku only (3 lines, 5-7-5 syllables)."
                ),
                HumanMessage(content=f"Write a haiku about {state['topic']}."),
            ]
        )
        return {"topic": state["topic"], "haiku": response.content}

    graph = StateGraph(HaikuState)
    graph.add_node("write_haiku", write_haiku_node)
    graph.add_edge(START, "write_haiku")
    graph.add_edge("write_haiku", END)
    return graph.compile()


def write_haiku(topic: str) -> str:
    result = _build_graph().invoke({"topic": topic, "haiku": ""})
    return str(result["haiku"])


def main():
    setup_instrumentation()
    print("=== Haiku Writer (LangGraph + OneAgent) ===\n")
    while True:
        topic = input("Topic [q to quit]: ").strip()
        if topic.lower() == "q":
            break
        print("\n" + write_haiku(topic) + "\n")


if __name__ == "__main__":
    main()
