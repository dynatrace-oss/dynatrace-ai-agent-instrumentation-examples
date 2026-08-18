import os


def init():
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"

    # By default Strands 1.x records message content as span *events* (legacy names
    # gen_ai.choice / gen_ai.tool.message / gen_ai.user.message), which the Dynatrace
    # AI Observability app does not read.
    # - gen_ai_latest_experimental: use the aggregated gen_ai.input/output.messages names.
    # - gen_ai_span_attributes_only: record that content as span *attributes* instead of
    #   events, so Dynatrace ingests the input/output messages.
    # Set before StrandsTelemetry initializes the tracer, which reads this at construction.
    os.environ.setdefault(
        "OTEL_SEMCONV_STABILITY_OPT_IN",
        "gen_ai_latest_experimental,gen_ai_span_attributes_only",
    )

    service_name = os.environ.get("OTEL_SERVICE_NAME", "aws-strands/openinference")
    # StrandsTelemetry builds the OTel resource from OTEL_SERVICE_NAME; ensure it is set.
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)

    # Default to the local OTel Collector; run-openpipeline overrides this to
    # send directly to Dynatrace and let OpenPipeline do the attribute remapping.
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        os.environ.pop("OTEL_EXPORTER_OTLP_HEADERS", None)

    # Strands 1.x telemetry: StrandsTelemetry registers the global tracer + meter
    # providers. The resource is built from OTEL_SERVICE_NAME; the exporters read the
    # OTEL_EXPORTER_OTLP_* env vars set above.
    from strands.telemetry import StrandsTelemetry
    from openinference.instrumentation.strands_agents import (
        StrandsAgentsToOpenInferenceProcessor,
    )

    telemetry = StrandsTelemetry()

    # StrandsAgentsToOpenInferenceProcessor mutates spans in-place, adding
    # OpenInference llm.*/tool.*/agent.* attributes alongside the gen_ai.* ones
    # Strands already emits natively — it does not remove the originals. Per the
    # package's own "Processor Ordering" note, it must be added to the tracer
    # provider *before* the exporter's span processor, so the OTLP exporter (added
    # next, via setup_otlp_exporter()) sees the already-transformed span.
    telemetry.tracer_provider.add_span_processor(StrandsAgentsToOpenInferenceProcessor())

    telemetry.setup_otlp_exporter().setup_meter(enable_otlp_exporter=True)
