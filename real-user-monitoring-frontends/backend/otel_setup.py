from __future__ import annotations

import os


def setup_otel(service_name: str = "rum-music-agent"):
    """
    Initialise OpenTelemetry traces + metrics and export to Dynatrace.
    Uses DT-ENDPOINT and DT-TOKEN from the environment (set via .env).
    Returns (tracer_provider, meter_provider).
    """
    dt_endpoint = os.environ.get("DT-ENDPOINT", "").rstrip("/")
    dt_api_token = os.environ.get("DT-TOKEN", "")

    if not dt_endpoint or not dt_api_token:
        print("[otel] DT-ENDPOINT or DT-TOKEN not set — OTel export disabled")
        return None, None

    otlp_base = f"{dt_endpoint}/api/v2/otlp"
    headers = {"Authorization": f"Api-Token {dt_api_token}"}

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

    print(f"[otel] Exporting to {otlp_base}")
    return tracer_provider, meter_provider
