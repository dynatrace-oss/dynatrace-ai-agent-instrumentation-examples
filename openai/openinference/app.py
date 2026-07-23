import os
import uuid
import openai
from openai import Stream
from openai.types.chat import ChatCompletionChunk
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("MODEL", "gpt-4o")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# For collector mode:     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# For OpenPipeline mode:  OTEL_EXPORTER_OTLP_ENDPOINT=https://<tenant>/api/v2/otlp
#                         OTEL_EXPORTER_OTLP_HEADERS=Authorization=Api-Token <token>
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "openai/openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    api_version = os.getenv("OPENAI_API_VERSION")
    if api_version:
        client = openai.AzureOpenAI(
            azure_endpoint=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_version=api_version,
        )
    else:
        client = openai.OpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    otel_trace.get_current_span().set_attribute("gen_ai.conversation.id", str(uuid.uuid4()))
    response: Stream[ChatCompletionChunk] = client.chat.completions.create(  # type: ignore[assignment]
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a haiku poet."},
            {"role": "user", "content": "Write a haiku."},
        ],
        max_completion_tokens=2000,
        temperature=1.0,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in response:
        if chunk.choices and (content := chunk.choices[0].delta.content):
            print(content, end="")
