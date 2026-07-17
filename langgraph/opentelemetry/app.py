import asyncio
import os
from typing import TypedDict

os.environ["TRACELOOP_TELEMETRY"] = "false"
os.environ.setdefault("OTEL_SERVICE_NAME", "langgraph")
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

from traceloop.sdk import Traceloop

_dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
_dt_token = os.environ.get("DT_API_TOKEN", "")
Traceloop.init(
    app_name="langgraph",
    api_endpoint=f"{_dt_base}/api/v2/otlp",
    headers={"Authorization": f"Api-Token {_dt_token}"},
    disable_batch=True,
    should_enrich_metrics=True,
)

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, StateGraph

_model = os.environ.get("MODEL", "genai-demo")

app = FastAPI()


class HaikuState(TypedDict):
    topic: str
    haiku: str


def _build_graph():
    llm = AzureChatOpenAI(
        azure_deployment=_model,
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-07-01-preview"),
    )

    def write_haiku(state: HaikuState) -> HaikuState:
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
    graph.add_node("write_haiku", write_haiku)
    graph.add_edge(START, "write_haiku")
    graph.add_edge("write_haiku", END)
    return graph.compile()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    def _call() -> str:
        graph = _build_graph()
        result = graph.invoke({"topic": "nature", "haiku": ""})
        return str(result["haiku"])

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
