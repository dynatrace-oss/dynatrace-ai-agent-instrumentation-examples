from __future__ import annotations

import os
from urllib.parse import urlparse


def setup_otel(service_name: str = "rum-music-agent", exporter_wrapper=None):
    """
    Initialise OpenTelemetry traces + metrics and export to Dynatrace.
    Uses DT_ENDPOINT and DT_TOKEN from the environment (set via .env).
    Returns (tracer_provider, meter_provider).

    Two export paths:
      - Collector (`make run`): OTEL_COLLECTOR_ENDPOINT (e.g.
        http://localhost:4318) routes through the local OTel Collector, which
        derives gen_ai.client.operation.duration and gen_ai.invoke_agent.duration
        from the spans and forwards everything to Dynatrace. The collector holds
        the DT token, so no Authorization header is sent from the app.
      - Direct (fallback): spans + metrics go straight to Dynatrace OTLP. Only
        the native gen_ai.client.token.usage metric is sent; no durations.

    OTEL_SERVICE_NAME overrides service_name.
    """
    service_name = os.environ.get("OTEL_SERVICE_NAME") or service_name
    collector_endpoint = os.environ.get("OTEL_COLLECTOR_ENDPOINT", "").rstrip("/")

    if collector_endpoint:
        otlp_base = collector_endpoint
        headers = {}
    else:
        dt_endpoint = os.environ.get("DT_ENDPOINT", "").rstrip("/")
        dt_api_token = os.environ.get("DT_API_TOKEN", "")

        if not dt_endpoint or not dt_api_token:
            print("[otel] DT_ENDPOINT or DT_API_TOKEN not set — OTel export disabled")
            return None, None

        parsed = urlparse(dt_endpoint)
        host = parsed.hostname or ""
        host_l = host.lower()
        if host_l == "apps.dynatrace.com" or host_l.endswith(".apps.dynatrace.com"):
            dt_endpoint = dt_endpoint.replace(".apps.dynatrace.com", ".live.dynatrace.com")
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
    raw_exporter = OTLPSpanExporter(endpoint=f"{otlp_base}/v1/traces", headers=headers)
    exporter = exporter_wrapper(raw_exporter) if exporter_wrapper else raw_exporter
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
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
