import os

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

print ("Initializing Traceloop...")
os.environ["CONFIG_FILE_PATH"] = "./config.yaml"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OTEL_URL = os.getenv("OTEL_URL")
OTEL_TOKEN = os.getenv("OTEL_TOKEN", "XYZ")
SERVICE_NAME = os.getenv("SERVICE_NAME", "fastapi-gateway")
TRACELOOP_BASE_URL = os.environ["TRACELOOP_BASE_URL"]
from traceloop.sdk import Traceloop

# Must run BEFORE litellm imports the proxy app
Traceloop.init(
    app_name="litellm-gateway",
    api_endpoint= TRACELOOP_BASE_URL,
    api_key="KEY",
    disable_batch=True,
    should_enrich_metrics=True,
    metrics_exporter=OTLPMetricExporter(endpoint="http://localhost:4317"),
)


# Instrument httpx BEFORE litellm import — LiteLLM creates httpx clients at import time
HTTPXClientInstrumentor().instrument()

import uvicorn
from litellm.proxy.proxy_server import app

FastAPIInstrumentor.instrument_app(app)

# Note: workers=1 only — Traceloop.init() only runs in this process
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4000, log_level="debug")


