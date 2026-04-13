#!/usr/bin/env python3
"""
Validate Dynatrace OTLP connectivity for OpenAI Codex CLI telemetry.

Sends a representative set of metrics and log events that mirror what
Codex exports during a real session, so you can verify end-to-end
data flow before enabling the integration.

Usage:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 test_connection.py
"""

import logging
import os
import sys
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load credentials
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

DT_API_TOKEN = os.environ.get("DT_API_TOKEN", "")
DT_OTEL_ENDPOINT = os.environ.get(
    "DT_OTEL_ENDPOINT", "https://<your-env-id>.live.dynatrace.com/api/v2/otlp"
)

# Normalise: strip trailing signal-specific path segments
for _suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
    if DT_OTEL_ENDPOINT.endswith(_suffix):
        DT_OTEL_ENDPOINT = DT_OTEL_ENDPOINT[: -len(_suffix)]

if not DT_API_TOKEN:
    print("ERROR: DT_API_TOKEN is not set. Add it to your .env file.")
    sys.exit(1)

HEADERS = {"Authorization": f"Api-Token {DT_API_TOKEN}"}


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
            print(f"  ✓  Endpoint reachable, token accepted (HTTP {code})")
            return True
        if code == 401:
            print(f"  ✗  Authentication failed (HTTP {code}). "
                  "Check that DT_API_TOKEN is correct.")
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


print(f"Sending test telemetry to: {DT_OTEL_ENDPOINT}")
print("─" * 60)

if not preflight_check(DT_OTEL_ENDPOINT, DT_API_TOKEN):
    print()
    print("Pre-flight check failed. Fix the issue above before continuing.")
    print("Hint: verify DT_OTEL_ENDPOINT and DT_API_TOKEN in your .env file.")
    sys.exit(1)

print()

# ---------------------------------------------------------------------------
# OpenTelemetry SDK setup
# ---------------------------------------------------------------------------
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

# Mimic the resource attributes Codex attaches to every signal
resource = Resource.create(
    {
        "service.name": "codex_cli_rs",   # DEFAULT_ORIGINATOR in Codex source
        "service.version": "test",
        "os.type": sys.platform,
    }
)

# Dynatrace requires DELTA temporality for metrics
os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"

reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(
        endpoint=f"{DT_OTEL_ENDPOINT}/v1/metrics",
        headers=HEADERS,
    ),
    export_interval_millis=5_000,
)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("codex_otel")

# ---------------------------------------------------------------------------
# Replicate Codex metrics (from codex-rs/otel/src/metrics/names.rs)
# ---------------------------------------------------------------------------

# Tool calls — histogram (count + duration)
tool_call_counter = meter.create_counter(
    "codex.tool.call",
    unit="count",
    description="Number of tool calls executed",
)
tool_call_duration = meter.create_histogram(
    "codex.tool.call.duration_ms",
    unit="ms",
    description="Tool call duration in milliseconds",
)

# API requests — histogram (count + duration)
api_request_counter = meter.create_counter(
    "codex.api_request",
    unit="count",
    description="Number of API requests made to the OpenAI Responses API",
)
api_request_duration = meter.create_histogram(
    "codex.api_request.duration_ms",
    unit="ms",
    description="API request duration in milliseconds",
)

# SSE streaming events
sse_event_counter = meter.create_counter(
    "codex.sse_event",
    unit="count",
    description="Number of SSE streaming events received",
)
sse_event_duration = meter.create_histogram(
    "codex.sse_event.duration_ms",
    unit="ms",
    description="SSE event processing duration in milliseconds",
)

# Responses API timing breakdowns (TTFT, TBT, overhead, inference)
responses_overhead = meter.create_histogram(
    "codex.responses_api_overhead.duration_ms",
    unit="ms",
    description="Responses API overhead excluding engine and client tool time",
)
responses_inference = meter.create_histogram(
    "codex.responses_api_inference_time.duration_ms",
    unit="ms",
    description="Responses API engine service total inference time",
)
responses_ttft = meter.create_histogram(
    "codex.responses_api_engine_service_ttft.duration_ms",
    unit="ms",
    description="Time to first token from engine service",
)

CONVERSATION_ID = str(uuid.uuid4())
COMMON_ATTRS = {
    "conversation.id": CONVERSATION_ID,
    "model": "o4-mini",
    "slug": "o4-mini",
    "originator": "codex_cli_rs",
    "auth_mode": "api_key",
    "session_source": "cli",
    "app.version": "test",
}

print("Recording test metrics …")

# Simulate a session: 1 conversation, 3 tool calls, 2 API requests, 10 SSE events
api_request_counter.add(2, COMMON_ATTRS)
api_request_duration.record(1420, {**COMMON_ATTRS, "status": "success"})
api_request_duration.record(980,  {**COMMON_ATTRS, "status": "success"})

tool_call_counter.add(3, {**COMMON_ATTRS, "tool_name": "shell"})
tool_call_duration.record(312,  {**COMMON_ATTRS, "tool_name": "shell", "status": "success"})
tool_call_duration.record(88,   {**COMMON_ATTRS, "tool_name": "shell", "status": "success"})
tool_call_duration.record(1205, {**COMMON_ATTRS, "tool_name": "shell", "status": "success"})

sse_event_counter.add(10, {**COMMON_ATTRS, "kind": "response.output_text.delta"})
sse_event_duration.record(12, {**COMMON_ATTRS, "kind": "response.output_text.delta"})

responses_overhead.record(45,   COMMON_ATTRS)
responses_inference.record(950, COMMON_ATTRS)
responses_ttft.record(310,      COMMON_ATTRS)

# ---------------------------------------------------------------------------
# Log events (mirrors Codex OtelManager event names)
# ---------------------------------------------------------------------------
logs_enabled = False
try:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

    log_exporter = OTLPLogExporter(
        endpoint=f"{DT_OTEL_ENDPOINT}/v1/logs",
        headers=HEADERS,
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    otel_handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(otel_handler)

    logger = logging.getLogger("codex_otel")

    print("Recording test log events …")

    # codex.conversation_starts
    logger.info(
        "codex.conversation_starts",
        extra={
            "event.name": "codex.conversation_starts",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conversation.id": CONVERSATION_ID,
            "model": "o4-mini",
            "slug": "o4-mini",
            "originator": "codex_cli_rs",
            "auth_mode": "api_key",
            "terminal.type": "unknown",
            "session_source": "cli",
            "approval_policy": "unless-allow-listed",
            "sandbox_policy": "workspace-write",
            "reasoning_effort": "medium",
            "app.version": "test",
        },
    )

    # codex.user_prompt
    logger.info(
        "codex.user_prompt",
        extra={
            "event.name": "codex.user_prompt",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conversation.id": CONVERSATION_ID,
            "model": "o4-mini",
            "originator": "codex_cli_rs",
            "app.version": "test",
        },
    )

    # codex.api_request (log event — distinct from the metric)
    logger.info(
        "codex.api_request",
        extra={
            "event.name": "codex.api_request",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conversation.id": CONVERSATION_ID,
            "model": "o4-mini",
            "slug": "o4-mini",
            "originator": "codex_cli_rs",
            "duration_ms": 1420,
            "input_tokens": 512,
            "output_tokens": 256,
            "app.version": "test",
        },
    )

    # codex.tool_decision
    logger.info(
        "codex.tool_decision",
        extra={
            "event.name": "codex.tool_decision",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conversation.id": CONVERSATION_ID,
            "tool_name": "shell",
            "decision": "approved",
            "decision_source": "config",
            "originator": "codex_cli_rs",
            "app.version": "test",
        },
    )

    # codex.tool_result
    logger.info(
        "codex.tool_result",
        extra={
            "event.name": "codex.tool_result",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conversation.id": CONVERSATION_ID,
            "tool_name": "shell",
            "success": "true",
            "duration_ms": 312,
            "originator": "codex_cli_rs",
            "app.version": "test",
        },
    )

    logs_enabled = True
except ImportError as exc:
    print(f"WARNING: Log export skipped – {exc}")

# ---------------------------------------------------------------------------
# Flush and report
# ---------------------------------------------------------------------------
print(f"\nFlushing … (waiting 7 s for the metric export interval)")
time.sleep(7)

errors = []
try:
    meter_provider.shutdown()
    print("✓  Metrics exported successfully")
except Exception as exc:  # noqa: BLE001
    print(f"✗  Metrics export error: {exc}")
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
print("  Metrics : Metrics browser → search 'codex'")
print("  Logs    : Log & Event Viewer → filter by service.name = codex_cli_rs")
print(f"  Conversation ID used in this test: {CONVERSATION_ID}")
