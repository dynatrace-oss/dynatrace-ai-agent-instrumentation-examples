import os
import uuid
from groq import Groq
from openinference.instrumentation.groq import GroqInstrumentor
from openinference.instrumentation import using_attributes
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("MODEL", "llama-3.1-8b-instant")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

GroqInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    # GROQ_BASE_URL is read automatically by the Groq client when set (e.g. by the e2e mock).
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    with using_attributes(session_id=str(uuid.uuid4())):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a haiku poet."},
                {"role": "user", "content": "Write a haiku."},
            ],
            max_tokens=2000,
            temperature=1.0,
        )
        print(response.choices[0].message.content)
