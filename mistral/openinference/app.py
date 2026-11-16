import os
import uuid
from mistralai.client import Mistral
from openinference.instrumentation.mistralai import MistralAIInstrumentor
from openinference.instrumentation import using_attributes
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("MODEL", "mistral-small-latest")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

MistralAIInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    kwargs = {"api_key": os.getenv("MISTRAL_API_KEY")}
    # MISTRAL_BASE_URL is used for internal testing only — the e2e mock points
    # it at a local stub. Unset in normal use (defaults to the public Mistral API).
    base_url = os.getenv("MISTRAL_BASE_URL")
    if base_url:
        kwargs["server_url"] = base_url
    client = Mistral(**kwargs)
    with using_attributes(session_id=str(uuid.uuid4())):
        response = client.chat.complete(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a haiku poet."},
                {"role": "user", "content": "Write a haiku."},
            ],
            max_tokens=2000,
            temperature=1.0,
        )
        print(response.choices[0].message.content)
