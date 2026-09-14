#!/usr/bin/env python3
"""Google Antigravity agent instrumented with the SDK's OpenTelemetry hooks.

The SDK does not auto-configure tracing: the OTel hooks in
`google.antigravity.utils.otel` have to be passed to LocalAgentConfig, and the
TracerProvider has to be set up by the application. Both happen here.

Those hooks trace the agent loop only. The model name, token counts and message
content live in Python objects at runtime and never reach a span, so they cannot
be added by a collector rule; the two hook subclasses below put them on the
invoke_agent span, which is what collector.yaml then derives
gen_ai.client.token.usage and gen_ai.client.operation.duration from.
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.models import DEFAULT_MODEL
from google.antigravity.utils import otel as otel_hooks

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "antigravity")
AGENT_NAME = "observability-assistant"
MODEL = os.getenv("MODEL") or DEFAULT_MODEL
SYSTEM_INSTRUCTIONS = "Call the registered tool once, then answer in two sentences."

# Prompt and response content is opt-in, per the OTel GenAI semconv. It defaults
# to on here because the point of the demo is to show the content in Dynatrace;
# set the variable to false to keep message bodies out of the spans.
CAPTURE_CONTENT = (
    os.getenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true").lower()
    == "true"
)


def content_to_text(content) -> str:
    """Flattens the SDK's Content union (str, media, or a sequence of both)."""
    parts = content if isinstance(content, (list, tuple)) else [content]
    return "\n".join(p if isinstance(p, str) else f"<{type(p).__name__}>" for p in parts)


class TracedPreTurnHook(otel_hooks.OTelPreTurnHook):
    """Adds request model and prompt content to the turn span the parent opens."""

    async def run(self, context, data):
        result = await super().run(context, data)
        span = context.get_state("turn_span")
        if span and span.is_recording():
            span.set_attribute("gen_ai.request.model", MODEL)
            if CAPTURE_CONTENT:
                span.set_attribute("gen_ai.system_instructions", SYSTEM_INSTRUCTIONS)
                span.set_attribute(
                    "gen_ai.input.messages",
                    json.dumps(
                        [
                            {
                                "role": "user",
                                "parts": [
                                    {"type": "text", "content": content_to_text(data)}
                                ],
                            }
                        ]
                    ),
                )
        return result


class TracedPostTurnHook(otel_hooks.OTelPostTurnHook):
    """Adds token usage and response content before the parent ends the turn span.

    Token usage is read from the live conversation rather than from the hook
    payload: the hooks carry no usage, and Conversation.last_turn_usage is a
    running diff against the turn's starting totals, so it is complete by the
    time this hook runs.
    """

    def __init__(self, agent_holder: dict):
        super().__init__()
        self._agent_holder = agent_holder

    async def run(self, context, data):
        span = context.get_state("turn_span")
        if span and span.is_recording():
            if CAPTURE_CONTENT:
                span.set_attribute(
                    "gen_ai.output.messages",
                    json.dumps(
                        [
                            {
                                "role": "assistant",
                                "parts": [{"type": "text", "content": data}],
                                "finish_reason": "stop",
                            }
                        ]
                    ),
                )
            agent = self._agent_holder.get("agent")
            usage = agent.conversation.last_turn_usage if agent else None
            if usage:
                # cached_content_token_count is a subset of prompt tokens, so it
                # is reported separately rather than added to the input total.
                # thoughts_token_count is billed as output and is not included in
                # candidates_token_count, so it is added to the output total.
                span.set_attribute(
                    "gen_ai.usage.input_tokens", usage.prompt_token_count or 0
                )
                span.set_attribute(
                    "gen_ai.usage.output_tokens",
                    (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0),
                )
                if usage.cached_content_token_count:
                    span.set_attribute(
                        "gen_ai.usage.cached_input_tokens",
                        usage.cached_content_token_count,
                    )
        await super().run(context, data)


def build_hooks(agent_holder: dict) -> list:
    """The SDK hook set with the two turn hooks swapped for the enriching ones.

    Subclassing rather than appending extra hooks is what guarantees ordering:
    the attributes have to be set after the turn span is opened and before it is
    ended, and the hook runner offers no way to express that.
    """
    swapped = []
    for hook in otel_hooks.get_otel_hooks(agent_name=AGENT_NAME):
        if isinstance(hook, otel_hooks.OTelPreTurnHook):
            swapped.append(TracedPreTurnHook(agent_name=AGENT_NAME))
        elif isinstance(hook, otel_hooks.OTelPostTurnHook):
            swapped.append(TracedPostTurnHook(agent_holder))
        else:
            swapped.append(hook)
    return swapped


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
    # The post-turn hook needs the Agent, which does not exist until after the
    # hooks are built, so it is handed a holder that is filled in below.
    agent_holder: dict = {}
    config = LocalAgentConfig(
        system_instructions=SYSTEM_INSTRUCTIONS,
        tools=[list_observability_signals],
        hooks=build_hooks(agent_holder),
        # The default policy set asks for interactive confirmation of run_command;
        # this demo only registers a Python function tool and runs unattended.
        policies=[],
        model=MODEL,
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
    )

    async with Agent(config) as agent:
        agent_holder["agent"] = agent
        prompt = (
            "Use list_observability_signals for Antigravity, "
            "then summarize why OTel spans are useful."
        )
        print(f"User: {prompt}")
        response = await agent.chat(prompt)
        print(f"Agent: {await response.text()}")
        usage = agent.conversation.total_usage
        print(f"Tokens: prompt={usage.prompt_token_count} total={usage.total_token_count}")


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    provider = configure_tracing()
    print(f"Exporting Antigravity traces to {otlp_base_url()} as service '{SERVICE_NAME}'")
    print(f"Model: {MODEL} | content capture: {CAPTURE_CONTENT}")
    try:
        asyncio.run(run_agent())
    finally:
        provider.force_flush()
        provider.shutdown()


if __name__ == "__main__":
    main()
