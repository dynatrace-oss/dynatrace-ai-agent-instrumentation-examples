import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

resource = Resource.create({SERVICE_NAME: "google-adk-samples"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    SimpleSpanProcessor(
        OTLPSpanExporter(
            endpoint=f"{os.environ['OTEL_ENDPOINT']}/v1/traces",
            headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
        )
    )
)
trace.set_tracer_provider(provider)

# Google ADK records OTel GenAI metrics (gen_ai.client.token.usage,
# gen_ai.client.operation.duration) against the global MeterProvider in
# google.adk.telemetry._metrics, but only if one is configured. Set it up here —
# before google.adk is imported below, so ADK's module-level instrument creation
# binds to this provider. Dynatrace OTLP metric ingest accepts delta temporality
# only; cumulative is rejected (HTTP 400).
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
meter_provider = MeterProvider(
    resource=resource,
    metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=f"{os.environ['OTEL_ENDPOINT']}/v1/metrics",
                headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
            )
        )
    ],
)
metrics.set_meter_provider(meter_provider)

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from agent import academic_coordinator

session_service = InMemorySessionService()

app = FastAPI()


class ResearchRequest(BaseModel):
    topic: str = "Attention is All You Need"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/research", response_class=PlainTextResponse)
async def research(req: ResearchRequest) -> str:
    runner = Runner(
        agent=academic_coordinator,
        app_name="google-adk-samples",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="google-adk-samples",
        user_id="e2e",
        session_id=str(uuid.uuid4()),
        state={"seminal_paper": req.topic},
    )
    message = Content(
        role="user",
        parts=[Part(text=f"Briefly summarize the key contributions of the paper: {req.topic}")],
    )

    async def _run() -> str:
        async for event in runner.run_async(
            user_id="e2e",
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        return part.text
        return ""

    result = await _run()
    if not result:
        raise HTTPException(status_code=500, detail="agent returned no response")
    return result
