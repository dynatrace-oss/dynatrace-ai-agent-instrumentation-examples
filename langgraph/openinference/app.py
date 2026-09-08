import asyncio
import os
from typing import TypedDict

from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

_service_name = os.environ.get("OTEL_SERVICE_NAME", "langgraph/openinference")
_resource = Resource.create({SERVICE_NAME: _service_name})
_tracer_provider = trace_sdk.TracerProvider(resource=_resource)
_tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_tracer_provider)
LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

_model = os.environ.get("MODEL", "genai-demo")

app = FastAPI()


class HaikuRequest(BaseModel):
    topic: str = "nature"


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
async def haiku(req: HaikuRequest | None = None) -> str:
    topic = req.topic if req else "nature"

    def _call() -> str:
        graph = _build_graph()
        result = graph.invoke({"topic": topic, "haiku": ""})
        return str(result["haiku"])

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
