import os
import uuid

import anthropic
from openinference.instrumentation import using_attributes
from openinference.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("ANTHROPIC_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# For collector mode:     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# For OpenPipeline mode:  OTEL_EXPORTER_OTLP_ENDPOINT=https://<tenant>/api/v2/otlp
#                         OTEL_EXPORTER_OTLP_HEADERS=Authorization=Api-Token <token>
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "anthropic/openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    # Same AWS Bedrock-hosted Claude access as anthropic/oneagent -- reuses the
    # AWS credentials already configured for e2e CI rather than requiring a
    # separate ANTHROPIC_API_KEY secret.
    client = anthropic.AnthropicBedrock(
        aws_region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    with using_attributes(session_id=str(uuid.uuid4())):
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            system="You are a haiku poet.",
            messages=[{"role": "user", "content": "Write a haiku."}],
        )
        print(response.content[0].text)
