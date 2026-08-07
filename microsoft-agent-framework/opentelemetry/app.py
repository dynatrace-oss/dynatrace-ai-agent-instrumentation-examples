import asyncio
import os
import uuid

from agent_framework import Agent, WorkflowBuilder, tool
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
    # Two export paths:
    #  - Direct (default): spans + metrics go straight to Dynatrace OTLP. The framework
    #    emits gen_ai.client.* natively, but NOT the agent/tool/workflow duration metrics.
    #  - Collector: set OTEL_COLLECTOR_ENDPOINT (e.g. http://localhost:4318) to route
    #    through the local OTel Collector, which derives gen_ai.invoke_agent.duration,
    #    gen_ai.execute_tool.duration and gen_ai.invoke_workflow.duration from the spans
    #    (spanmetrics) and forwards everything to Dynatrace. The collector holds the DT
    #    token, so no Authorization header is sent from the app.
    collector_endpoint = os.getenv("OTEL_COLLECTOR_ENDPOINT", "").rstrip("/")

    os.environ["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"

    if collector_endpoint:
        traces_endpoint = f"{collector_endpoint}/v1/traces"
        metrics_endpoint = f"{collector_endpoint}/v1/metrics"
        auth_header = ""
    else:
        dt_endpoint = _require_env("DT_ENDPOINT").rstrip("/")
        dt_api_token = _require_env("DT_API_TOKEN")
        auth_header = f"Authorization=Api-Token {dt_api_token}"
        # Traces — spans with gen_ai.* attributes including gen_ai.input/output.messages
        traces_endpoint = f"{dt_endpoint}/api/v2/otlp/v1/traces"
        # Metrics — gen_ai.client.operation.duration (latency charts) and gen_ai.token.type (cost lanes)
        metrics_endpoint = f"{dt_endpoint}/api/v2/otlp/v1/metrics"

    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = traces_endpoint
    os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = metrics_endpoint
    if auth_header:
        os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = auth_header
        os.environ["OTEL_EXPORTER_OTLP_METRICS_HEADERS"] = auth_header

    # Dynatrace requires delta temporality; the SDK default (cumulative) returns 400.
    os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

    os.environ.setdefault("OTEL_SERVICE_NAME", "microsoft-agent-framework")


# A tool call is what produces the `execute_tool` span (gen_ai.operation.name =
# "execute_tool") that the collector turns into gen_ai.execute_tool.duration.
# The reading is canned so the demo stays deterministic and dependency-free.
@tool(description="Return the current golden signals for a monitored service.")
def get_service_health(service: str) -> str:
    """Return a canned golden-signal reading for the given service."""
    return (
        f"service={service} error_rate=4.2% p95_latency=1180ms "
        f"throughput=310rpm saturation=0.71"
    )


async def main() -> None:
    load_dotenv()

    _configure_dynatrace_otlp()

    configure_otel_providers(enable_sensitive_data=True)

    model = os.getenv("MODEL", "gpt-5.4-mini")
    openai_base = _require_env("OPENAI_API_BASE")
    openai_key = _require_env("OPENAI_API_KEY")
    api_version = os.getenv("OPENAI_API_VERSION", "2025-04-01-preview")
    temperature = float(os.getenv("TEMPERATURE", "1"))
    conversation_id = str(uuid.uuid4())

    client = OpenAIChatCompletionClient(
        model=model,
        azure_endpoint=_derive_azure_endpoint(openai_base),
        api_key=openai_key,
        api_version=api_version,
    )

    default_options = {
        "temperature": temperature,
        "conversation_id": conversation_id,
    }

    # Agent.run() goes through AgentTelemetryLayer, which sets gen_ai.agent.name on the span.
    # Direct client.get_response() only hits ChatTelemetryLayer and never emits gen_ai.agent.name.
    #
    # Two agents chained in a workflow, so the trace carries the full span set the
    # GenAI agent metrics are defined over: workflow.run > invoke_agent > chat /
    # execute_tool. A single agent would only ever produce invoke_agent + chat.
    analyst = Agent(
        client=client,
        name="observability-analyst-agent",
        description="Reads service golden signals and summarizes what is wrong.",
        instructions=(
            "You diagnose service health. Always call the get_service_health tool "
            "for the service named in the request, then summarize the findings in "
            "two sentences."
        ),
        tools=[get_service_health],
        default_options=default_options,
    )

    poet = Agent(
        client=client,
        name="observability-haiku-agent",
        description="Writes concise haikus about software observability.",
        instructions=(
            "You write concise haikus about software observability. Turn the "
            "diagnosis you are given into a single haiku."
        ),
        default_options=default_options,
    )

    workflow = (
        WorkflowBuilder(name="observability-diagnosis-workflow", start_executor=analyst)
        .add_chain([analyst, poet])
        .build()
    )

    prompt = "How healthy is the checkout-service right now?"
    print(f"User: {prompt}")
    result = await workflow.run(prompt)
    for output in result.get_outputs():
        print(f"Assistant: {output}")

    # Explicitly flush and shut down providers before exit so BatchSpanProcessor and
    # PeriodicExportingMetricReader finish their work before atexit hooks fire.
    for provider in (otel_trace.get_tracer_provider(), otel_metrics.get_meter_provider()):
        if hasattr(provider, "force_flush"):
            provider.force_flush()
        if hasattr(provider, "shutdown"):
            provider.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
