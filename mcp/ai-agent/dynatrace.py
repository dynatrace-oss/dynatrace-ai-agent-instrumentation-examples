import os
from traceloop.sdk import Traceloop
from utils import read_secret

def setup_tracing(service_name):
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    token = read_secret("dynatrace_otel")
    headers = { "Authorization": f"Api-Token {token}" }
    OTEL_ENDPOINT = os.environ.get(
        "OTEL_ENDPOINT", "https://wkf10640.live.dynatrace.com/api/v2/otlp" #manually configure your DT tenant here
    )
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