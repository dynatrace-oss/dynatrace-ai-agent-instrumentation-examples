import litellm
import logging
import os
import time
from fastapi import FastAPI, HTTPException
from litellm.integrations.opentelemetry import OpenTelemetry as LiteLLMOTel
from opentelemetry import metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from pydantic import BaseModel
from typing import Optional
from traceloop.sdk import Traceloop

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Instrument httpx BEFORE litellm import — LiteLLM creates httpx clients at import time
HTTPXClientInstrumentor().instrument()

import uvicorn
from litellm.proxy.proxy_server import app

# Must run BEFORE litellm imports the proxy app
COLLECTOR_BASE_URL = os.environ["COLLECTOR_BASE_URL"]

# Optional LLM provider keys — set in environment to enable each provider
# Grok (xAI): use model prefix "xai/", e.g. "xai/grok-2-latest"
# Groq:       use model prefix "groq/", e.g. "groq/llama-3.3-70b-versatile"
if os.environ.get("XAI_API_KEY"):
    litellm.xai_api_key = os.environ["XAI_API_KEY"]
if os.environ.get("GROQ_API_KEY"):
    litellm.groq_api_key = os.environ["GROQ_API_KEY"]

litellm.callbacks = [LiteLLMOTel()]

# Route Python logs to the local OTLP collector (same endpoint as metrics/spans)
_log_provider = LoggerProvider()
_log_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint="COLLECTOR_BASE_URL"))
)
set_logger_provider(_log_provider)
logging.basicConfig(level=logging.INFO)
logging.getLogger().addHandler(LoggingHandler(logger_provider=_log_provider))

logger = logging.getLogger("litellm-gateway")

Traceloop.init(
    app_name="litellm-gateway",
    api_endpoint=TRACELOOP_BASE_URL,
    api_key="KEY",
    disable_batch=True,
    should_enrich_metrics=True,
    metrics_exporter=OTLPMetricExporter(endpoint="http://localhost:4317"),
)

# Register LiteLLM's built-in OTEL callback — automatically captures gen_ai.*
# attributes (model, tokens, cost, finish reasons, provider) for every completion call

# Custom metrics — Traceloop has already registered the global MeterProvider above
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

FastAPIInstrumentor.instrument_app(app)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    kwargs = {"model": request.model, "messages": messages}
    if request.max_tokens is not None:
        kwargs["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature

    attrs = {"model": request.model}
    logger.info("chat request: model=%s", request.model)
    _request_counter.add(1, attrs)
    start = time.time()
    try:
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
