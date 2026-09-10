#!/usr/bin/env python3
"""Google Antigravity agent instrumented with the SDK's OpenTelemetry hooks.

The SDK does not auto-configure tracing: the OTel hooks in
`google.antigravity.utils.otel` have to be passed to LocalAgentConfig, and the
TracerProvider has to be set up by the application. Both happen here.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.utils import otel as otel_hooks

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "antigravity")
AGENT_NAME = "observability-assistant"


def otlp_base_url() -> str:
    """Dynatrace OTLP base URL, with any signal-specific suffix stripped."""
    url = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
    for suffix in ("/v1/traces", "/v1/metrics", "/v1/logs"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def configure_tracing() -> TracerProvider:
    endpoint = otlp_base_url()
    if not endpoint:
        sys.exit("OTEL_EXPORTER_OTLP_ENDPOINT is not set; run `source activate.sh` first.")

    headers = {}
    token = os.getenv("DT_API_TOKEN")
    # Against a local collector the credentials live in the collector, not here.
    if token and "127.0.0.1" not in endpoint and "localhost" not in endpoint:
        headers["Authorization"] = f"Api-Token {token}"

    # The SDK sets gen_ai.operation.name, gen_ai.agent.name and gen_ai.tool.name
    # on its spans but never a provider, so it is pinned on the resource.
    resource = Resource.create(
        {"service.name": SERVICE_NAME, "gen_ai.provider.name": "google"}
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers))
    )
    trace.set_tracer_provider(provider)
    return provider


def list_observability_signals(topic: str) -> str:
    """Lists the observability signals available for a topic."""
    return f"Signals available for {topic}: traces, metrics, logs, and events."


async def run_agent() -> None:
    config = LocalAgentConfig(
        system_instructions="Call the registered tool once, then answer in two sentences.",
        tools=[list_observability_signals],
        hooks=otel_hooks.get_otel_hooks(agent_name=AGENT_NAME),
        # The default policy set asks for interactive confirmation of run_command;
        # this demo only registers a Python function tool and runs unattended.
        policies=[],
        model=os.getenv("MODEL") or None,
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
    )

    async with Agent(config) as agent:
        prompt = (
            "Use list_observability_signals for Antigravity, "
            "then summarize why OTel spans are useful."
        )
        print(f"User: {prompt}")
        response = await agent.chat(prompt)
        print(f"Agent: {await response.text()}")


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    provider = configure_tracing()
    print(f"Exporting Antigravity traces to {otlp_base_url()} as service '{SERVICE_NAME}'")
    try:
        asyncio.run(run_agent())
    finally:
        provider.force_flush()
        provider.shutdown()


if __name__ == "__main__":
    main()
