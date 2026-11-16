import litellm
import logging
import os
import time
import uuid
from fastapi import FastAPI, HTTPException
from openinference.instrumentation import TraceConfig, using_session
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel
from typing import Optional

# Dynatrace OTLP metric ingest accepts delta temporality only; cumulative is rejected (HTTP 400).
# Must be set before the OTLP metric exporter is constructed below.
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

COLLECTOR_BASE_URL = os.environ["COLLECTOR_BASE_URL"]
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "litellm-gateway-fastapi")
resource = Resource.create({"service.name": SERVICE_NAME})

# App-owned OTLP/gRPC export of traces, metrics, and logs to the local Collector.
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=COLLECTOR_BASE_URL, insecure=True))
)
trace.set_tracer_provider(tracer_provider)

metrics.set_meter_provider(
    MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=COLLECTOR_BASE_URL, insecure=True))
        ],
    )
)

_log_provider = LoggerProvider(resource=resource)
_log_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=COLLECTOR_BASE_URL, insecure=True))
)
set_logger_provider(_log_provider)
logging.basicConfig(level=logging.INFO)
logging.getLogger().addHandler(LoggingHandler(logger_provider=_log_provider))

logger = logging.getLogger("litellm-gateway")

# Instrument httpx BEFORE litellm import — LiteLLM creates httpx clients at import time
HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

# OpenInference owns the LLM spans; enable_genai_semconv adds gen_ai.* alongside llm.*.
# Content capture is enabled. Review before production use.
LiteLLMInstrumentor().instrument(
    tracer_provider=tracer_provider,
    config=TraceConfig(enable_genai_semconv=True),
)

# Optional LLM provider keys — set in environment to enable each provider
# Grok (xAI): use model prefix "xai/", e.g. "xai/grok-2-latest"
# Groq:       use model prefix "groq/", e.g. "groq/llama-3.3-70b-versatile"
if os.environ.get("XAI_API_KEY"):
    litellm.xai_api_key = os.environ["XAI_API_KEY"]
if os.environ.get("GROQ_API_KEY"):
    litellm.groq_api_key = os.environ["GROQ_API_KEY"]

# Custom request metrics (OpenInference emits spans only).
_meter = metrics.get_meter("litellm-gateway")
_request_counter = _meter.create_counter(
    "llm.requests",
    description="Total number of chat completion requests",
)
_error_counter = _meter.create_counter(
    "llm.errors",
    description="Total number of failed chat completion requests",
)
_duration_histogram = _meter.create_histogram(
    "llm.request.duration",
    unit="s",
    description="Duration of chat completion requests",
)
_token_counter = _meter.create_counter(
    "llm.tokens",
    description="Total tokens used, split by type (input/output)",
)

app = FastAPI()

# Drop the ASGI "http receive"/"http send" sub-spans; keep only the server span.
FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, exclude_spans=["receive", "send"])


@app.get("/health")
async def health():
    return {"status": "ok"}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    conversation_id: Optional[str] = None


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    kwargs = {"model": request.model, "messages": messages}
    if request.max_tokens is not None:
        kwargs["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    session_id = request.conversation_id or str(uuid.uuid4())

    attrs = {"model": request.model}
    logger.info("chat request: model=%s", request.model)
    _request_counter.add(1, attrs)
    start = time.time()
    try:
        with using_session(session_id):
            response = litellm.completion(**kwargs)
        _duration_histogram.record(time.time() - start, attrs)
        usage = getattr(response, "usage", None)
        if usage:
            _token_counter.add(usage.prompt_tokens or 0, {**attrs, "token.type": "input"})
            _token_counter.add(usage.completion_tokens or 0, {**attrs, "token.type": "output"})
        logger.info("chat response: model=%s id=%s", request.model, response.id)
        return response
    except Exception as e:
        _duration_histogram.record(time.time() - start, attrs)
        _error_counter.add(1, attrs)
        logger.error("chat completion failed: model=%s error=%s", request.model, e)
        raise HTTPException(status_code=500, detail=str(e))
