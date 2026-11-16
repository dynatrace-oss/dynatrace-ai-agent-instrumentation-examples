#!/usr/bin/env python3
"""Sends a representative Antigravity trace to Dynatrace without calling Gemini.

Use this to verify endpoint, token and network path before running the agent.
The span shapes mirror what google.antigravity.utils.otel emits: a session root,
an "invoke_agent <name>" turn, an "antigravity.step.<n>" step, and an
"execute_tool <name>" tool call.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

AGENT_NAME = "observability-assistant"
TOOL_NAME = "list_observability_signals"


def strip_signal_suffix(url: str) -> str:
    url = url.rstrip("/")
    for suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collector",
        action="store_true",
        help="send to a local collector on http://127.0.0.1:4318 instead of Dynatrace",
    )
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))

    if args.collector:
        endpoint, headers = "http://127.0.0.1:4318", {}
    else:
        endpoint = strip_signal_suffix(os.getenv("DT_OTEL_ENDPOINT", ""))
        token = os.getenv("DT_API_TOKEN", "")
        if not endpoint or not token:
            print(
                "Set DT_OTEL_ENDPOINT and DT_API_TOKEN, or pass --collector",
                file=sys.stderr,
            )
            return 2
        headers = {"Authorization": f"Api-Token {token}"}

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "antigravity"),
            "gen_ai.provider.name": "google",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers))
    )
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("google-antigravity-sdk")

    with tracer.start_as_current_span("antigravity.session"):
        with tracer.start_as_current_span(
            f"invoke_agent {AGENT_NAME}",
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": AGENT_NAME,
            },
        ):
            with tracer.start_as_current_span(
                "antigravity.step.0",
                attributes={"antigravity.step.index": 0},
            ):
                with tracer.start_as_current_span(
                    f"execute_tool {TOOL_NAME}",
                    attributes={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": TOOL_NAME,
                    },
                ):
                    time.sleep(0.01)

    provider.force_flush()
    provider.shutdown()
    print(f"Sent Antigravity test spans to {endpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
