import os
import uuid

from dotenv import load_dotenv

load_dotenv()

# ADK's experimental semconv path writes gen_ai.input.messages,
# gen_ai.output.messages and gen_ai.system_instructions as OTel span
# attributes. Without the opt-in, ADK only writes content into GCP-internal
# blobs (gcp.vertex.agent.llm_request/response), which are not OTel semconv.
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

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
    # The coordinator's value is delegation: it reaches academic_websearch_agent and
    # academic_newresearch_agent through AgentTool. Asking only for a summary of a
    # well-known paper lets the model answer from its own weights, producing a trace
    # with no execute_tool span at all, so the derived
    # gen_ai.execute_tool.duration metric is missing on those runs.
    #
    # Ask for recent citing work instead, which the coordinator cannot answer without
    # the websearch tool. That makes the tool call part of the demo's happy path
    # rather than a coin flip.
    message = Content(
        role="user",
        parts=[
            Part(
                text=(
                    f"Summarize the key contributions of the paper: {req.topic}. "
                    "Then use your tools to find recent papers citing it and to suggest "
                    "future research directions based on what you find."
                )
            )
        ],
    )

    async def _run() -> str:
        # Drain the runner rather than returning from inside the loop. Returning early
        # abandons the async generator, which ADK reports as "Root node
        # academic_coordinator was cancelled" and OTel as a "Failed to detach context
        # ... was created in a different Context" ValueError: the generator is closed
        # while spans are still open, so any span that had not ended yet is never
        # exported. Keeping the first final response but consuming the stream to
        # completion lets every span end normally.
        answer = ""
        async for event in runner.run_async(
            user_id="e2e",
            session_id=session.id,
            new_message=message,
        ):
            if not answer and event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        answer = part.text
                        break
        return answer

    result = await _run()
    if not result:
        raise HTTPException(status_code=500, detail="agent returned no response")
    return result
