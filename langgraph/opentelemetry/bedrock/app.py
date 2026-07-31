import asyncio
import os
from typing import TypedDict

os.environ["TRACELOOP_TELEMETRY"] = "false"
os.environ.setdefault("OTEL_SERVICE_NAME", "langgraph/opentelemetry/bedrock")
# Dynatrace ingests delta metrics only; export delta temporality from the SDK.
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")

from traceloop.sdk import Traceloop

# Export target. When OTEL_EXPORTER_OTLP_ENDPOINT is set (see the Makefile `run`
# target), spans go to a local Dynatrace OpenTelemetry Collector that forwards
# them to Dynatrace. Otherwise export straight to Dynatrace.
_collector = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
if _collector:
    Traceloop.init(
        app_name="langgraph/opentelemetry/bedrock",
        api_endpoint=_collector,
        headers={},
        disable_batch=True,
        should_enrich_metrics=True,
    )
else:
    _dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
    _dt_token = os.environ.get("DT_API_TOKEN", "")
    Traceloop.init(
        app_name="langgraph/opentelemetry/bedrock",
        api_endpoint=f"{_dt_base}/api/v2/otlp",
        headers={"Authorization": f"Api-Token {_dt_token}"},
        disable_batch=True,
        should_enrich_metrics=True,
    )

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_aws import ChatBedrock
from langgraph.graph import END, START, StateGraph

_model = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

app = FastAPI()


class HaikuRequest(BaseModel):
    topic: str = "nature"


class HaikuState(TypedDict):
    topic: str
    haiku: str


def _build_graph():
    llm = ChatBedrock(
        model_id=_model,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
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
