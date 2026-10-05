import os

from openinference.instrumentation import TraceConfig
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

os.environ["CONFIG_FILE_PATH"] = os.getenv("CONFIG_FILE_PATH", "./config.yaml")
COLLECTOR_BASE_URL = os.getenv("COLLECTOR_BASE_URL", "http://localhost:4318").rstrip("/")
SERVICE_NAME = os.getenv("SERVICE_NAME", "litellm-gateway")

tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": SERVICE_NAME})
)
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{COLLECTOR_BASE_URL}/v1/traces"))
)
trace.set_tracer_provider(tracer_provider)

# Instrument HTTPX first because LiteLLM can create clients at import time.
HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)

# Content capture is intentionally enabled. Review before production use.
# GenAI emission is additive; the Collector removes legacy attributes.
LiteLLMInstrumentor().instrument(
    tracer_provider=tracer_provider,
    config=TraceConfig(
        enable_genai_semconv=True,
        hide_inputs=False,
        hide_outputs=False,
        hide_input_messages=False,
        hide_output_messages=False,
    ),
)

import uvicorn
from litellm.proxy.proxy_server import app



# Unauthenticated liveness probe. LiteLLM's own /health needs the master key and
# calls every configured model, so register this route ahead of the proxy routes.
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


app.router.routes.insert(0, app.router.routes.pop())

FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, exclude_spans=["receive", "send"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info", workers=1)
