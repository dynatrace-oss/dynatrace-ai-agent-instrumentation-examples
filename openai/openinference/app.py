import os
import uuid
import openai
from openai import Stream
from openai.types.chat import ChatCompletionChunk
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import context, trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes
from opentelemetry.trace import SpanKind


class SessionSpanProcessor(SpanProcessor):
    """Stamps session.id on every span so gen_ai_normalizer can map it to gen_ai.conversation.id."""

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id

    def on_start(self, span: trace_sdk.Span, parent_context: Context | None = None) -> None:
        span.set_attribute("session.id", self._session_id)

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

MODEL: str = os.environ.get("MODEL", "gpt-4o")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# For collector mode:     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# For OpenPipeline mode:  OTEL_EXPORTER_OTLP_ENDPOINT=https://<tenant>/api/v2/otlp
#                         OTEL_EXPORTER_OTLP_HEADERS=Authorization=Api-Token <token>
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "openinference"}))

session_id = os.getenv("SESSION_ID", str(uuid.uuid4()))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SessionSpanProcessor(session_id))
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

if __name__ == "__main__":
    api_version = os.getenv("OPENAI_API_VERSION")
    client = openai.OpenAI(
        base_url=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
        **({"default_query": {"api-version": api_version}} if api_version else {}),
    )
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        "openai.chat",
        kind=SpanKind.CLIENT,
        attributes={"gen_ai.request.model": MODEL},
    ):
        response: Stream[ChatCompletionChunk] = client.chat.completions.create(  # type: ignore[assignment]
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
            max_completion_tokens=20,
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in response:
            if chunk.choices and (content := chunk.choices[0].delta.content):
                print(content, end="")
