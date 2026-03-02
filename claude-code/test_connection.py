#!/usr/bin/env python3
"""
Validate Dynatrace OTLP connectivity for Claude Code telemetry.

Sends a representative set of metrics and log events that mirror what
Claude Code exports during a real session, so you can verify end-to-end
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
    "DT_OTEL_ENDPOINT", "https://xbw95514.live.dynatrace.com/api/v2/otlp"
)

# Normalise: strip trailing signal-specific path segments so we always work
# with the base endpoint (https://…/api/v2/otlp)
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
            # Empty body rejected – but the endpoint exists and auth succeeded
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

# Mimic the resource attributes Claude Code attaches to every signal
resource = Resource.create(
    {
        "service.name": "claude-code",
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
meter = metrics.get_meter("com.anthropic.claude_code")

# ---------------------------------------------------------------------------
# Replicate Claude Code metrics
# ---------------------------------------------------------------------------
session_counter = meter.create_counter(
    "claude_code.session.count",
    unit="count",
    description="Count of CLI sessions started",
)
token_counter = meter.create_counter(
    "claude_code.token.usage",
    unit="tokens",
    description="Number of tokens used",
)
cost_counter = meter.create_counter(
    "claude_code.cost.usage",
    unit="USD",
    description="Cost of the Claude Code session in USD",
)
lines_counter = meter.create_counter(
    "claude_code.lines_of_code.count",
    unit="count",
    description="Lines of code modified",
)
active_time_counter = meter.create_counter(
    "claude_code.active_time.total",
    unit="s",
    description="Total active time in seconds",
)

SESSION_ID = str(uuid.uuid4())
COMMON_ATTRS = {
    "session.id": SESSION_ID,
    "user.id": "test-user",
    "app.version": "test",
}

print("Recording test metrics …")
session_counter.add(1, COMMON_ATTRS)
token_counter.add(512,  {**COMMON_ATTRS, "type": "input",       "model": "claude-sonnet-4-6"})
token_counter.add(256,  {**COMMON_ATTRS, "type": "output",      "model": "claude-sonnet-4-6"})
token_counter.add(1024, {**COMMON_ATTRS, "type": "cacheRead",   "model": "claude-sonnet-4-6"})
cost_counter.add(0.001, {**COMMON_ATTRS, "model": "claude-sonnet-4-6"})
lines_counter.add(10,   {**COMMON_ATTRS, "type": "added"})
lines_counter.add(2,    {**COMMON_ATTRS, "type": "removed"})
active_time_counter.add(30, {**COMMON_ATTRS, "type": "cli"})
active_time_counter.add(5,  {**COMMON_ATTRS, "type": "user"})

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

    logger = logging.getLogger("com.anthropic.claude_code")
    PROMPT_ID = str(uuid.uuid4())

    print("Recording test log events …")
    logger.info(
        "claude_code.user_prompt",
        extra={
            "event.name": "user_prompt",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event.sequence": 1,
            "prompt.id": PROMPT_ID,
            "prompt_length": 42,
            **COMMON_ATTRS,
        },
    )
    logger.info(
        "claude_code.api_request",
        extra={
            "event.name": "api_request",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event.sequence": 2,
            "prompt.id": PROMPT_ID,
            "model": "claude-sonnet-4-6",
            "cost_usd": 0.001,
            "duration_ms": 1500,
            "input_tokens": 512,
            "output_tokens": 256,
            "cache_read_tokens": 1024,
            "cache_creation_tokens": 0,
            "speed": "normal",
            **COMMON_ATTRS,
        },
    )
    logger.info(
        "claude_code.tool_result",
        extra={
            "event.name": "tool_result",
            "event.timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event.sequence": 3,
            "prompt.id": PROMPT_ID,
            "tool_name": "Read",
            "success": "true",
            "duration_ms": 12,
            "decision_type": "accept",
            "decision_source": "config",
            **COMMON_ATTRS,
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
print("  Metrics : Metrics browser → search 'claude_code'")
print("  Logs    : Log & Event Viewer → filter by service.name = claude-code")
print("  Notebook: AI & LLM Observability dashboard (if configured)")
print(f"  Session ID used in this test: {SESSION_ID}")
