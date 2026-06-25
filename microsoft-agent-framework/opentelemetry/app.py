import asyncio
import os
import uuid

from agent_framework import Agent
from agent_framework.observability import configure_otel_providers
from agent_framework.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _derive_azure_endpoint(base_url: str) -> str:
    # OPENAI_API_BASE points to:
    # https://<resource>.openai.azure.com/openai/deployments/<deployment>
    marker = "/openai/"
    if marker in base_url:
        return base_url.split(marker, 1)[0]
    return base_url.rstrip("/")


def _configure_dynatrace_otlp() -> None:
    dt_endpoint = _require_env("DT_ENDPOINT").rstrip("/")
    dt_api_token = _require_env("DT_API_TOKEN")
    auth_header = f"Authorization=Api-Token {dt_api_token}"

    os.environ["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"

    # Traces — spans with gen_ai.* attributes including gen_ai.input/output.messages
    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"{dt_endpoint}/api/v2/otlp/v1/traces"
    os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = auth_header

    # Metrics — gen_ai.client.operation.duration (latency charts) and gen_ai.token.type (cost lanes)
    os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = f"{dt_endpoint}/api/v2/otlp/v1/metrics"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_HEADERS"] = auth_header
    # Dynatrace requires delta temporality; the SDK default (cumulative) returns 400.
    os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

    os.environ.setdefault("OTEL_SERVICE_NAME", "microsoft-agent-framework")


async def main() -> None:
    load_dotenv()

    _configure_dynatrace_otlp()

    configure_otel_providers(enable_sensitive_data=True)

    model = os.getenv("MODEL", "gpt-5.4-mini")
    openai_base = _require_env("OPENAI_API_BASE")
    openai_key = _require_env("OPENAI_API_KEY")
    api_version = os.getenv("OPENAI_API_VERSION", "2025-04-01-preview")

    client = OpenAIChatCompletionClient(
        model=model,
        azure_endpoint=_derive_azure_endpoint(openai_base),
        api_key=openai_key,
        api_version=api_version,
    )

    # Agent.run() goes through AgentTelemetryLayer, which sets gen_ai.agent.name on the span.
    # Direct client.get_response() only hits ChatTelemetryLayer and never emits gen_ai.agent.name.
    agent = Agent(
        client=client,
        name="observability-haiku-agent",
        description="Writes concise haikus about software observability.",
        instructions="You write concise haikus about software observability.",
        default_options={
            "conversation_id": str(uuid.uuid4()),
        },
    )

    prompt = "Write a haiku about observability."
    print(f"User: {prompt}")
    result = await agent.run(prompt)
    print(f"Assistant: {result.text}")

    # Explicitly flush and shut down providers before exit so BatchSpanProcessor and
    # PeriodicExportingMetricReader finish their work before atexit hooks fire.
    for provider in (otel_trace.get_tracer_provider(), otel_metrics.get_meter_provider()):
        if hasattr(provider, "force_flush"):
            provider.force_flush()
        if hasattr(provider, "shutdown"):
            provider.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
