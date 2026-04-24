#!/usr/bin/env python3
"""
Validate Dynatrace OTLP connectivity for OpenCode telemetry.

Sends representative trace spans that mirror what OpenCode exports during
a real session, so you can verify end-to-end data flow before enabling the
integration.

Usage:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 test_connection.py
"""

import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load credentials
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

DT_API_TOKEN = os.environ.get("DT_API_TOKEN", "")
DT_OTEL_ENDPOINT = os.environ.get("DT_OTEL_ENDPOINT", "")

if not DT_API_TOKEN:
    raw_headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    for part in raw_headers.split(","):
        if "Authorization=Api-Token " in part:
            DT_API_TOKEN = part.split("Authorization=Api-Token ", 1)[1].strip()
            break

if not DT_OTEL_ENDPOINT:
    DT_OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

for _suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
    if DT_OTEL_ENDPOINT.endswith(_suffix):
        DT_OTEL_ENDPOINT = DT_OTEL_ENDPOINT[: -len(_suffix)]

if not DT_API_TOKEN or not DT_OTEL_ENDPOINT or "<YOUR" in DT_OTEL_ENDPOINT:
    print("ERROR: Set DT_API_TOKEN and DT_OTEL_ENDPOINT in .env (or OTEL_EXPORTER_OTLP_* vars).")
    sys.exit(1)

HEADERS = {"Authorization": f"Api-Token {DT_API_TOKEN}"}


# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------
def preflight_check(endpoint: str, token: str) -> bool:
    traces_url = f"{endpoint}/v1/traces"
    print(f"Pre-flight check: POST {traces_url}")
    req = urllib.request.Request(
        traces_url,
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
            print(f"  ✗  Authentication failed (HTTP {code}). Check DT_API_TOKEN.")
            return False
        if code == 403:
            print(f"  ✗  Authorisation denied (HTTP {code}). Token needs openTelemetryTrace.ingest scope.")
            return False
        if code == 404:
            print(f"  ✗  Endpoint not found (HTTP {code}). Check DT_OTEL_ENDPOINT. Response: {body}")
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
    print("\nPre-flight check failed. Fix the issue above before continuing.")
    sys.exit(1)

print()

# ---------------------------------------------------------------------------
# OTel SDK — traces only (OpenCode sends traces direct to DT via protobuf)
# ---------------------------------------------------------------------------
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create(
    {
        "service.name": "opencode",
        "service.version": "test",
        "opencode.client": "test",
        "opencode.process_role": "main",
        "opencode.run_id": str(uuid.uuid4()),
        "service.instance.id": str(uuid.uuid4()),
        "deployment.environment.name": "stable",
    }
)

exporter = OTLPSpanExporter(
    endpoint=f"{DT_OTEL_ENDPOINT}/v1/traces",
    headers=HEADERS,
)
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("opencode")

SESSION_ID = str(uuid.uuid4())
MESSAGE_ID = str(uuid.uuid4())

print("Recording test spans …")

# Simulate a complete OpenCode interaction: session → LLM call → tool execution

with tracer.start_as_current_span(
    "Session.create",
    attributes={"session.id": SESSION_ID},
) as session_span:
    time.sleep(0.01)

    with tracer.start_as_current_span(
        "LLM.run",
        attributes={
            "session.id": SESSION_ID,
            "providerID": "anthropic",
            "modelID": "claude-sonnet-4-5",
            "agent": "coder",
            "mode": "auto",
            "small": "false",
        },
    ) as llm_span:
        time.sleep(0.05)

        with tracer.start_as_current_span(
            "Tool.execute",
            attributes={
                "session.id": SESSION_ID,
                "message.id": MESSAGE_ID,
                "tool.name": "read",
                "tool.call_id": str(uuid.uuid4()),
            },
        ):
            time.sleep(0.02)

        with tracer.start_as_current_span(
            "Tool.execute",
            attributes={
                "session.id": SESSION_ID,
                "message.id": MESSAGE_ID,
                "tool.name": "write",
                "tool.call_id": str(uuid.uuid4()),
            },
        ):
            time.sleep(0.03)

    with tracer.start_as_current_span(
        "SessionProcessor.create",
        attributes={"session.id": SESSION_ID},
    ):
        time.sleep(0.005)

print("Flushing spans …")
provider.shutdown()
print("✓  Traces exported successfully")
print()
print("─" * 60)
print("Done! Open your Dynatrace tenant and look for:")
print("  Distributed Traces → filter by service.name = opencode")
print("  Span names: Session.create, LLM.run, Tool.execute")
print(f"  Session ID: {SESSION_ID}")
