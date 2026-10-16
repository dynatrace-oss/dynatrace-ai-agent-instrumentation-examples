import os

from llama_index.core.llms import ChatMessage
from llama_index.llms.azure_openai import AzureOpenAI
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
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
    initial_resource=Resource.create({service_attributes.SERVICE_NAME: "llamaindex-openinference-demo"}),
)

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# LlamaIndexInstrumentor hooks LlamaIndex's instrumentation dispatcher and emits
# OpenInference-shaped spans for every LLM call.
LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "genai-demo")
    llm = AzureOpenAI(
        engine=deployment,
        model="gpt-4o-mini",  # used by LlamaIndex for context-window metadata only
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("OPENAI_API_VERSION", "2024-07-01-preview"),
    )

    topic = os.environ.get("TOPIC", "observability")
    response = llm.chat(
        [
            ChatMessage(role="system", content="You are a haiku poet."),
            ChatMessage(role="user", content=f"Write a haiku about {topic}."),
        ]
    )
    print(response.message.content)
