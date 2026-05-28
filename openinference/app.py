import os
import openai
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes

MODEL = os.environ.get("MODEL", "gpt-5-nano-2025-08-07")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# For collector mode:     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# For OpenPipeline mode:  OTEL_EXPORTER_OTLP_ENDPOINT=https://<tenant>/api/v2/otlp
#                         OTEL_EXPORTER_OTLP_HEADERS=Authorization=Api-Token <token>
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create({service_attributes.SERVICE_NAME: "openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    client = openai.OpenAI(
        base_url=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY")
        )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Write a haiku."}],
        max_completion_tokens=20,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in response:
        if chunk.choices and (content := chunk.choices[0].delta.content):
            print(content, end="")
