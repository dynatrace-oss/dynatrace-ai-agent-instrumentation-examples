import os
import uuid

from google import genai
from google.genai import types
from openinference.instrumentation import using_attributes
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("MODEL") or "gemini-3.1-flash-lite"

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# OTEL_SERVICE_NAME, when set, overrides the service name below.
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "gemini/openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    # The client reads GOOGLE_API_KEY (or GEMINI_API_KEY) from the environment.
    client = genai.Client()
    with using_attributes(session_id=str(uuid.uuid4())):
        response = client.models.generate_content(
            model=MODEL,
            contents="Write a haiku.",
            config=types.GenerateContentConfig(
                system_instruction="You are a haiku poet.",
                max_output_tokens=2000,
                temperature=1.0,
            ),
        )
        print(response.text)
