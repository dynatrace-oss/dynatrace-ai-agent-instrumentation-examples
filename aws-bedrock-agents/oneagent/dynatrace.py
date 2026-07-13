import os

def init():
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    app_name = os.environ.get("OTEL_SERVICE_NAME", "aws-bedrock-agents/oneagent")
    # Route through local otelcol (started by make run); collector forwards to DT.
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    from traceloop.sdk import Traceloop
    Traceloop.init(
        app_name=app_name,
        disable_batch=False,
        should_enrich_metrics=True,
    )
