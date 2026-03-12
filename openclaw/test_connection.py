#!/usr/bin/env python3
"""
Validate Dynatrace OTLP connectivity for OpenClaw telemetry.

Sends a representative set of metrics, traces, and log events that mirror
what the OpenClaw diagnostics-otel plugin exports during a real session,
so you can verify end-to-end data flow before enabling the integration.

Usage:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 test_connection.py <ENDPOINT> <API_TOKEN>

Example:
    python3 test_connection.py https://abc12345.live.dynatrace.com/api/v2/otlp dt0c01.XXXXXXXX.YYYYYYYY
"""

import logging
import os
import sys
import time
import urllib.request
import urllib.error
import uuid

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
if len(sys.argv) < 3:
    print("Usage: python3 test_connection.py <ENDPOINT> <API_TOKEN>")
    print()
    print("  ENDPOINT   Dynatrace OTLP endpoint (e.g. https://<env-id>.live.dynatrace.com/api/v2/otlp)")
    print("  API_TOKEN  Dynatrace API token with openTelemetryTrace.ingest scope")
    sys.exit(1)

OTEL_ENDPOINT = sys.argv[1]
API_TOKEN = sys.argv[2]

# Normalise: strip trailing signal-specific path segments so we always work
# with the base endpoint (https://…/api/v2/otlp)
for _suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
    if OTEL_ENDPOINT.endswith(_suffix):
        OTEL_ENDPOINT = OTEL_ENDPOINT[: -len(_suffix)]

HEADERS = {"Authorization": f"Api-Token {API_TOKEN}"}


# ---------------------------------------------------------------------------
# Pre-flight connectivity check
# ---------------------------------------------------------------------------
def preflight_check(endpoint: str, token: str) -> bool:
    """
    Send an empty POST to the metrics endpoint to confirm the Dynatrace
    tenant is reachable and the API token is accepted.

    Expected responses:
      400  – endpoint reachable, token valid (empty body is invalid protobuf)
      401  – endpoint reachable, token invalid or missing scope
      403  – endpoint reachable, token lacks openTelemetryTrace.ingest scope
      404  – endpoint path does not exist (wrong tenant ID or deactivated tenant)
    """
    metrics_url = f"{endpoint}/v1/metrics"
    print(f"Pre-flight check: POST {metrics_url}")

    req = urllib.request.Request(
        metrics_url,
        data=b"",
        headers={
            "Authorization": f"Api-Token {token}",
            "Content-Type": "application/x-protobuf",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
        body = exc.read().decode(errors="replace")
        if code == 400:
            # Empty body rejected – but the endpoint exists and auth succeeded
            print(f"  ✓  Endpoint reachable, token accepted (HTTP {code})")
            return True
        if code == 401:
            print(f"  ✗  Authentication failed (HTTP {code}). "
                  "Check that API_TOKEN is correct.")
            return False
        if code == 403:
            print(
                f"  ✗  Authorisation denied (HTTP {code}). "
                "Ensure the token has the 'openTelemetryTrace.ingest' scope."
            )
            return False
        if code == 404:
            print(
                f"  ✗  Endpoint not found (HTTP {code}). "
                "The tenant may be deactivated or the URL is wrong. "
                f"Response: {body}"
            )
            return False
        print(f"  ✗  Unexpected HTTP {code}: {body}")
        return False
    except urllib.error.URLError as exc:
        print(f"  ✗  Connection error: {exc.reason}")
        return False

    print(f"  ✓  HTTP {code}")
    return True


print(f"Sending test telemetry to: {OTEL_ENDPOINT}")
print("─" * 60)

if not preflight_check(OTEL_ENDPOINT, API_TOKEN):
    print()
    print("Pre-flight check failed. Fix the issue above before continuing.")
    print("Hint: verify OTEL_ENDPOINT and API_TOKEN in your .env file.")
    sys.exit(1)

print()

# ---------------------------------------------------------------------------
# OpenTelemetry SDK setup
# ---------------------------------------------------------------------------
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

# Mimic the resource attributes the OpenClaw diagnostics-otel plugin attaches
resource = Resource.create(
    {
        "service.name": "openclaw-gateway",
        "service.version": "test",
        "os.type": sys.platform,
    }
)

# Dynatrace requires DELTA temporality for metrics
os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"

# --- Metrics ---
reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(
        endpoint=f"{OTEL_ENDPOINT}/v1/metrics",
        headers=HEADERS,
    ),
    export_interval_millis=5_000,
)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("openclaw.diagnostics")

# --- Traces ---
span_exporter = OTLPSpanExporter(
    endpoint=f"{OTEL_ENDPOINT}/v1/traces",
    headers=HEADERS,
)
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("openclaw.diagnostics")

# ---------------------------------------------------------------------------
# Replicate OpenClaw metrics
# ---------------------------------------------------------------------------
token_counter = meter.create_counter(
    "openclaw.tokens",
    unit="tokens",
    description="Number of tokens used",
)
cost_counter = meter.create_counter(
    "openclaw.cost.usd",
    unit="USD",
    description="Estimated model cost in USD",
)
run_duration = meter.create_histogram(
    "openclaw.run.duration_ms",
    unit="ms",
    description="Agent run duration",
)
context_tokens = meter.create_histogram(
    "openclaw.context.tokens",
    unit="tokens",
    description="Context window usage",
)
webhook_counter = meter.create_counter(
    "openclaw.webhook.received",
    unit="count",
    description="Webhooks received",
)
message_counter = meter.create_counter(
    "openclaw.message.processed",
    unit="count",
    description="Messages processed",
)

SESSION_ID = str(uuid.uuid4())
COMMON_ATTRS = {
    "session.id": SESSION_ID,
    "service.name": "openclaw-gateway",
}

print("Recording test metrics …")
token_counter.add(512, {**COMMON_ATTRS, "type": "input", "model": "claude-sonnet-4-6"})
token_counter.add(256, {**COMMON_ATTRS, "type": "output", "model": "claude-sonnet-4-6"})
token_counter.add(1024, {**COMMON_ATTRS, "type": "cache", "model": "claude-sonnet-4-6"})
cost_counter.add(0.001, {**COMMON_ATTRS, "model": "claude-sonnet-4-6"})
run_duration.record(1500, COMMON_ATTRS)
context_tokens.record(4096, COMMON_ATTRS)
webhook_counter.add(1, {**COMMON_ATTRS, "source": "telegram"})
message_counter.add(1, COMMON_ATTRS)

# ---------------------------------------------------------------------------
# Replicate OpenClaw trace spans
# ---------------------------------------------------------------------------
print("Recording test trace spans …")
with tracer.start_as_current_span("openclaw.model.usage", attributes={
    **COMMON_ATTRS,
    "model": "claude-sonnet-4-6",
    "input_tokens": 512,
    "output_tokens": 256,
    "cost_usd": 0.001,
}) as span:
    time.sleep(0.05)  # simulate latency

with tracer.start_as_current_span("openclaw.webhook.processed", attributes={
    **COMMON_ATTRS,
    "source": "telegram",
}) as span:
    time.sleep(0.02)

with tracer.start_as_current_span("openclaw.message.processed", attributes={
    **COMMON_ATTRS,
    "message.type": "text",
}) as span:
    time.sleep(0.01)

# ---------------------------------------------------------------------------
# Log events
# ---------------------------------------------------------------------------
logs_enabled = False
try:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

    log_exporter = OTLPLogExporter(
        endpoint=f"{OTEL_ENDPOINT}/v1/logs",
        headers=HEADERS,
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    otel_handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(otel_handler)

    logger = logging.getLogger("openclaw.diagnostics")

    print("Recording test log events …")
    logger.info(
        "openclaw.model.usage",
        extra={
            "event.name": "model.usage",
            "model": "claude-sonnet-4-6",
            "input_tokens": 512,
            "output_tokens": 256,
            "cost_usd": 0.001,
            "duration_ms": 1500,
            **COMMON_ATTRS,
        },
    )
    logger.info(
        "openclaw.webhook.received",
        extra={
            "event.name": "webhook.received",
            "source": "telegram",
            **COMMON_ATTRS,
        },
    )
    logger.info(
        "openclaw.message.processed",
        extra={
            "event.name": "message.processed",
            "message.type": "text",
            "duration_ms": 350,
            **COMMON_ATTRS,
        },
    )
    logs_enabled = True
except ImportError as exc:
    print(f"WARNING: Log export skipped – {exc}")

# ---------------------------------------------------------------------------
# Flush and report
# ---------------------------------------------------------------------------
print(f"\nFlushing … (waiting 7 s for the export interval)")
time.sleep(7)

errors = []
try:
    meter_provider.shutdown()
    print("✓  Metrics exported successfully")
except Exception as exc:  # noqa: BLE001
    print(f"✗  Metrics export error: {exc}")
    errors.append(exc)

try:
    tracer_provider.shutdown()
    print("✓  Traces exported successfully")
except Exception as exc:  # noqa: BLE001
    print(f"✗  Traces export error: {exc}")
    errors.append(exc)

if logs_enabled:
    try:
        logger_provider.shutdown()
        print("✓  Log events exported successfully")
    except Exception as exc:  # noqa: BLE001
        print(f"✗  Log export error: {exc}")
        errors.append(exc)

if errors:
    sys.exit(1)

print()
print("─" * 60)
print("Done! Open your Dynatrace tenant and look for:")
print("  Metrics : Metrics browser → search 'openclaw'")
print("  Traces  : Distributed traces → filter by service.name = openclaw-gateway")
print("  Logs    : Log & Event Viewer → filter by service.name = openclaw-gateway")
print(f"  Session ID used in this test: {SESSION_ID}")
