from __future__ import annotations

import os


def setup_otel(service_name: str = "pydantic-ai-music-agent"):
    """
    Initialise OpenTelemetry traces + metrics and export them to Dynatrace.

    Uses DT-ENDPOINT and DT-TOKEN from the environment (set via .env).
    Returns (tracer_provider, meter_provider) so callers can pass them into
    pydantic-ai's InstrumentationSettings.
    """
    # Two export paths:
    #  - Direct (default): spans + metrics go straight to Dynatrace OTLP. pydantic-ai
    #    emits gen_ai.client.token.usage natively, but NOT operation.duration, so the
    #    duration metric must be backfilled server-side (openpipeline-pydantic-ai.yaml).
    #  - Collector: set OTEL_COLLECTOR_ENDPOINT (e.g. http://localhost:4318) to route
    #    through the local OTel Collector, which derives gen_ai.client.operation.duration
    #    from the LLM spans (span_metrics) and forwards everything to Dynatrace. The
    #    collector holds the DT token, so no Authorization header is sent from the app.
    collector_endpoint = os.environ.get("OTEL_COLLECTOR_ENDPOINT", "").rstrip("/")

    if collector_endpoint:
        otlp_base = collector_endpoint
        headers = {}
        target = f"collector {collector_endpoint}"
    else:
        dt_endpoint = os.environ.get("DT_ENDPOINT", "").rstrip("/")
        dt_api_token = os.environ.get("DT_API_TOKEN", "")

        if not dt_endpoint or not dt_api_token:
            print("[otel] DT-ENDPOINT or DT-TOKEN not set — OTel export disabled")
            return None, None

        otlp_base = f"{dt_endpoint}/api/v2/otlp"
        headers = {"Authorization": f"Api-Token {dt_api_token}"}
        target = otlp_base

    # Dynatrace requires delta temporality for metrics
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"

    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
            "gen_ai.agent.name": service_name,
            "telemetry.sdk.name": "pydantic-ai",
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{otlp_base}/v1/traces", headers=headers)
        )
    )
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{otlp_base}/v1/metrics", headers=headers)
            )
        ],
        resource=resource,
    )
    metrics.set_meter_provider(meter_provider)

    print(f"[otel] Exporting to {target}")
    return tracer_provider, meter_provider
