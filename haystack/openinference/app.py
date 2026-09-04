import os

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import AzureOpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret
from openinference.instrumentation.haystack import HaystackInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import (
    OsResourceDetector,
    OTELResourceDetector,
    ProcessResourceDetector,
    Resource,
    get_aggregated_resources,
)
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.semconv.attributes import service_attributes

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# For collector mode:     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# For OpenPipeline mode:  OTEL_EXPORTER_OTLP_ENDPOINT=https://<tenant>/api/v2/otlp
#                         OTEL_EXPORTER_OTLP_HEADERS=Authorization=Api-Token <token>
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(
    detectors=detectors,
    initial_resource=Resource.create({service_attributes.SERVICE_NAME: "haystack-openinference-demo"}),
)

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# HaystackInstrumentor wraps Pipeline.run and every component's run method directly
# (via wrapt), independent of Haystack's own haystack.tracing abstraction — unlike
# the haystack/oneagent demo, there is no tracer to disable here.
HaystackInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    generator = AzureOpenAIChatGenerator(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "genai-demo"),
        api_key=Secret.from_env_var("AZURE_OPENAI_API_KEY"),
        api_version=os.environ.get("OPENAI_API_VERSION", "2024-07-01-preview"),
    )

    pipeline = Pipeline()
    pipeline.add_component(
        "prompt",
        ChatPromptBuilder(
            template=[
                ChatMessage.from_system("You are a haiku poet."),
                ChatMessage.from_user("Write a haiku about {{ topic }}."),
            ]
        ),
    )
    pipeline.add_component("llm", generator)
    pipeline.connect("prompt.prompt", "llm.messages")

    result = pipeline.run({"prompt": {"topic": "observability"}})
    print(result["llm"]["replies"][0].text)
