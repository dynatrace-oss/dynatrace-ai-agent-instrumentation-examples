import os


def init():
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    service_name = os.environ.get("OTEL_SERVICE_NAME", "aws-strands/opentelemetry")
    # StrandsTelemetry builds the OTel resource from OTEL_SERVICE_NAME; ensure it is set.
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)

    # Default to the local OTel Collector; run-openpipeline overrides this to
    # send directly to Dynatrace and let OpenPipeline do the attribute remapping.
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        os.environ.pop("OTEL_EXPORTER_OTLP_HEADERS", None)

    # Strands 1.x telemetry: StrandsTelemetry registers the global tracer + meter
    # providers. The resource is built from OTEL_SERVICE_NAME; the exporters read the
    # OTEL_EXPORTER_OTLP_* env vars set above. Replaces the pre-1.0
    # get_tracer(service_name=...) singleton call, which was removed in the 1.x API.
    #
    # Note: Strands emits its own strands.* metrics (e.g. strands.event_loop.input.tokens),
    # not the OTel semconv gen_ai.client.* metrics the AI Observability app charts — the
    # app's metric tiles still rely on OpenPipeline span-to-metric extraction for Strands.
    from strands.telemetry import StrandsTelemetry

    StrandsTelemetry().setup_otlp_exporter().setup_meter(enable_otlp_exporter=True)
