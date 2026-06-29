import os


def init():
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    service_name = os.environ.get("OTEL_SERVICE_NAME", "aws-strands/opentelemetry")

    # Send to the local OTel Collector; it handles auth and attribute remapping.
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
    os.environ.pop("OTEL_EXPORTER_OTLP_HEADERS", None)

    # Pre-initialize Strands' tracer singleton so it picks up our endpoint and
    # service name. Without this, Strands lazily defaults to service_name="strands-agents".
    from strands.telemetry.tracer import get_tracer as _get_strands_tracer
    _get_strands_tracer(service_name=service_name)
