import os

def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception as e:
        print("No token was provided")
        print(e)
        return ""

def init():
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    token = read_secret("dynatrace_otel") or os.environ.get("DT_API_TOKEN", "")
    headers = {"Authorization": f"Api-Token {token}"}
    OTEL_ENDPOINT = os.environ.get(
        "OTEL_ENDPOINT", "https://wkf10640.live.dynatrace.com/api/v2/otlp" #manually configure your DT tenant here
    )
    if OTEL_ENDPOINT.endswith("/v1/traces"):
        OTEL_ENDPOINT = OTEL_ENDPOINT[0 : OTEL_ENDPOINT.find("/v1/traces")]
    if OTEL_ENDPOINT.endswith("/v1/metrics"):
        OTEL_ENDPOINT = OTEL_ENDPOINT[0 : OTEL_ENDPOINT.find("/v1/metrics")]
    print(f"Sending data to {OTEL_ENDPOINT}")

    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{OTEL_ENDPOINT}"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Api-Token {token},"

    service_name = os.environ.get("OTEL_SERVICE_NAME", "aws-strands/opentelemetry")

    # Pre-initialize Strands' tracer singleton so it picks up our OTLP env vars and
    # uses the correct service name. Without this, Strands lazily initializes with
    # service_name="strands-agents" on first Agent() call.
    from strands.telemetry.tracer import get_tracer as _get_strands_tracer
    _strands_tracer = _get_strands_tracer(service_name=service_name)

    # Strands emits gen_ai.prompt / gen_ai.completion instead of the OTel GenAI
    # convention (gen_ai.input.messages / gen_ai.output.messages) that the
    # Dynatrace AI Observability app queries. This processor adds the expected names.
    if _strands_tracer.tracer_provider is not None:
        from opentelemetry.sdk.trace import SpanProcessor

        class _AttrRemapper(SpanProcessor):
            def on_start(self, span, parent_context=None):
                pass

            def on_end(self, span):
                # span.attributes is a MappingProxyType (read-only); use _attributes
                attrs = getattr(span, "_attributes", None)
                if not attrs:
                    return
                if "gen_ai.prompt" in attrs and "gen_ai.input.messages" not in attrs:
                    attrs["gen_ai.input.messages"] = attrs["gen_ai.prompt"]
                if "gen_ai.completion" in attrs and "gen_ai.output.messages" not in attrs:
                    attrs["gen_ai.output.messages"] = attrs["gen_ai.completion"]

            def shutdown(self):
                pass

            def force_flush(self, timeout_millis: int = 30000) -> bool:
                return True

        _strands_tracer.tracer_provider.add_span_processor(_AttrRemapper())

    from opentelemetry import metrics
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": service_name, "service.version": "0.0.0"})
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{OTEL_ENDPOINT}/v1/metrics", headers=headers)
    )
    metrics_provider = MeterProvider(metric_readers=[reader], resource=resource)
    metrics.set_meter_provider(metrics_provider)