import os
from traceloop.sdk import Traceloop
from utils import read_secret

def setup_tracing(service_name):
    # this disable traceloop posthog integration and does NOT impact
    # the data reported to Dynatrace
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    token = os.environ.get("DT_API_TOKEN") or read_secret("dynatrace_otel")
    headers = { "Authorization": f"Api-Token {token}" }
    OTEL_ENDPOINT = os.environ.get("OTEL_ENDPOINT", "").rstrip("/")
    if not OTEL_ENDPOINT:
        raise ValueError("OTEL_ENDPOINT environment variable is required")
    resource = {
        "gen_ai.agent.name": service_name,
        "service.name": service_name,
        "service.version": "0.0.1"
    }
    Traceloop.init(
        app_name=service_name,
        api_endpoint=OTEL_ENDPOINT,
        headers=headers,
        resource_attributes=resource,
    )