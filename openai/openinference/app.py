import os
import uuid

from openai import AzureOpenAI
from openinference.instrumentation import TraceConfig, using_attributes
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def configure_tracing() -> TracerProvider:
    if os.getenv("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "").lower() != "true":
        raise RuntimeError(
            "Set OPENINFERENCE_ENABLE_GENAI_SEMCONV=true so OpenInference emits "
            "OTel GenAI semantic-convention attributes required by AI Observability."
        )

    endpoint = required("DT_ENDPOINT").rstrip("/") + "/api/v2/otlp/v1/traces"
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"Authorization": f"Api-Token {required('DT_API_TOKEN')}"},
    )
    provider = TracerProvider(
        resource=Resource.create({"service.name": "azure-openai-openinference"})
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    OpenAIInstrumentor().instrument(
        tracer_provider=provider,
        config=TraceConfig(),
    )
    return provider


def main() -> None:
    provider = configure_tracing()
    client = AzureOpenAI(
        azure_endpoint=required("AZURE_OPENAI_ENDPOINT"),
        api_key=required("AZURE_OPENAI_API_KEY"),
        api_version=required("AZURE_OPENAI_API_VERSION"),
    )

    with using_attributes(session_id=str(uuid.uuid4())):
        response = client.chat.completions.create(
            model=required("AZURE_OPENAI_DEPLOYMENT"),
            messages=[{"role": "user", "content": "Write a haiku about observability."}],
            max_completion_tokens=100,
        )
        print(response.choices[0].message.content)

    provider.force_flush()
    provider.shutdown()


if __name__ == "__main__":
    main()
