#!/usr/bin/env python3
"""
Validate Dynatrace OTLP connectivity for Kiro's native OpenTelemetry export.

Kiro (AWS's AI coding assistant) only exports OTel data as an
Enterprise-admin-configured daily batch (see
https://kiro.dev/docs/enterprise/monitor-and-track/user-activity/opentelemetry/).
There is no local CLI flag to trigger a real export on demand, so this
script replicates the documented metric names, attributes, and resource
attributes exactly, letting you evaluate what a Kiro dashboard would look
like without a live AWS/Kiro Enterprise deployment.

Usage:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 test_connection.py
"""

import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
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

for _suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
    if DT_OTEL_ENDPOINT.endswith(_suffix):
        DT_OTEL_ENDPOINT = DT_OTEL_ENDPOINT[: -len(_suffix)]

if not DT_API_TOKEN:
    print("ERROR: DT_API_TOKEN is not set. Add it to your .env file.")
    sys.exit(1)

HEADERS = {"Authorization": f"Api-Token {DT_API_TOKEN}"}


def preflight_check(endpoint: str, token: str) -> bool:
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
            print(f"  ✗  Authentication failed (HTTP {code}). Check DT_API_TOKEN.")
            return False
        if code == 403:
            print(f"  ✗  Authorisation denied (HTTP {code}). Ensure the token has 'metrics.ingest' scope.")
            return False
        if code == 404:
            print(f"  ✗  Endpoint not found (HTTP {code}). Response: {body}")
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

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

# Resource attributes Kiro attaches to every export (per the enterprise docs)
resource = Resource.create(
    {
        "service.name": "kiro-enterprise",
        "kiro.profile.arn": "arn:aws:codewhisperer:us-east-1:123456789012:profile/kiro-demo-profile",
        "kiro.profile.id": "kiro-demo-profile",
        "kiro.account.id": "123456789012",
    }
)

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
meter = metrics.get_meter("kiro_otel_demo")

# ---------------------------------------------------------------------------
# Replicate the five kiro.daily.* Sum counters from the Kiro enterprise docs
# ---------------------------------------------------------------------------
credits_counter = meter.create_counter(
    "kiro.daily.credits", unit="1", description="Credits used"
)
overage_credits_counter = meter.create_counter(
    "kiro.daily.overage_credits", unit="1", description="Overage credits used"
)
messages_counter = meter.create_counter(
    "kiro.daily.messages", unit="1", description="Total messages"
)
conversations_counter = meter.create_counter(
    "kiro.daily.conversations", unit="1", description="Chat conversations"
)
model_messages_counter = meter.create_counter(
    "kiro.daily.model_messages", unit="1", description="Messages per model"
)

activity_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

# Synthetic org: three users across the three documented client types
USERS = [
    {
        "kiro.user.id": "u-alice-0001",
        "kiro.user.email": "alice@example.com",
        "kiro.client.type": "KIRO_IDE",
        "kiro.user.new": False,
        "kiro.subscription.tier": "Pro",
        "kiro.usage.limit": 1000,
        "kiro.overage.enabled": True,
        "kiro.overage.cap": 50.0,
        "credits": 82,
        "overage_credits": 5,
        "messages": 140,
        "conversations": 12,
        "model_messages": {"claude-sonnet-4-5": 95, "claude-haiku-4-5": 45},
    },
    {
        "kiro.user.id": "u-bob-0002",
        "kiro.user.email": "bob@example.com",
        "kiro.client.type": "KIRO_CLI",
        "kiro.user.new": True,
        "kiro.subscription.tier": "Enterprise",
        "kiro.usage.limit": 5000,
        "kiro.overage.enabled": False,
        "kiro.overage.cap": 0.0,
        "credits": 210,
        "overage_credits": 0,
        "messages": 305,
        "conversations": 28,
        "model_messages": {"claude-sonnet-4-5": 305},
    },
    {
        "kiro.user.id": "u-carla-0003",
        "kiro.user.email": "carla@example.com",
        "kiro.client.type": "PLUGIN",
        "kiro.user.new": False,
        "kiro.subscription.tier": "Pro",
        "kiro.usage.limit": 1000,
        "kiro.overage.enabled": True,
        "kiro.overage.cap": 25.0,
        "credits": 34,
        "overage_credits": 0,
        "messages": 51,
        "conversations": 6,
        "model_messages": {"claude-haiku-4-5": 51},
    },
]

print("Recording synthetic kiro.daily.* datapoints "
      f"for activity date {activity_date} ...")

for user in USERS:
    common_attrs = {
        "kiro.user.id": user["kiro.user.id"],
        "kiro.user.email": user["kiro.user.email"],
        "kiro.client.type": user["kiro.client.type"],
        "kiro.user.new": user["kiro.user.new"],
        "kiro.subscription.tier": user["kiro.subscription.tier"],
        "kiro.usage.limit": user["kiro.usage.limit"],
        "kiro.overage.enabled": user["kiro.overage.enabled"],
        "kiro.overage.cap": user["kiro.overage.cap"],
        "date": activity_date,
    }

    credits_counter.add(user["credits"], common_attrs)
    overage_credits_counter.add(user["overage_credits"], common_attrs)
    messages_counter.add(user["messages"], common_attrs)
    conversations_counter.add(user["conversations"], common_attrs)

    for model_name, count in user["model_messages"].items():
        model_attrs = {**common_attrs, "kiro.model.name": model_name}
        model_messages_counter.add(count, model_attrs)

print(f"\nFlushing ... (waiting 7 s for the metric export interval)")
time.sleep(7)

try:
    meter_provider.shutdown()
    print("✓  Metrics exported successfully")
except Exception as exc:  # noqa: BLE001
    print(f"✗  Metrics export error: {exc}")
    sys.exit(1)

print()
print("─" * 60)
print("Done! Verify in Dynatrace with:")
print("  timeseries mm = sum(kiro.daily.model_messages), by:{kiro.model.name}, from: -2h")
print(f"  Synthetic activity date used: {activity_date}")
