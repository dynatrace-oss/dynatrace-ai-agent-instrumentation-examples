import contextvars
import json
import os
import uuid

from google import genai
from google.genai import types
from openinference.instrumentation import using_session
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("MODEL") or "gemini-3.1-flash-lite"
SYSTEM_PROMPT = "You are a haiku poet. Answer with a single haiku and nothing else."

_system_instructions: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "system_instructions", default=None)


class SystemInstructionsSpanProcessor(SpanProcessor):
    """Sets gen_ai.system_instructions on google-genai spans.

    OpenInference keeps the system instruction only as an input message and
    does not lift it to gen_ai.system_instructions.
    """

    def on_start(self, span, parent_context=None):
        value = _system_instructions.get()
        scope = span.instrumentation_scope.name if span.instrumentation_scope else ""
        if value and "google_genai" in scope:
            span.set_attribute("gen_ai.system_instructions", value)

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# OTEL_SERVICE_NAME, when set, overrides the service name below.
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "gemini/openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SystemInstructionsSpanProcessor())
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)


def chat(client: genai.Client, history: list[types.Content], message: str) -> str:
    """Send one user turn with the conversation history and record the reply."""
    history.append(types.Content(role="user", parts=[types.Part(text=message)]))
    token = _system_instructions.set(json.dumps([{"type": "text", "content": SYSTEM_PROMPT}]))
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=2000,
                temperature=0.7,
            ),
        )
    finally:
        _system_instructions.reset(token)
    text = response.text or ""
    history.append(types.Content(role="model", parts=[types.Part(text=text)]))
    return text


if __name__ == "__main__":
    # The client reads GOOGLE_API_KEY (or GEMINI_API_KEY) from the environment.
    client = genai.Client()
    topic = os.environ.get("TOPIC") or "the sea"
    # Reuse CONVERSATION_ID to continue a conversation; a new id is generated when unset.
    conversation_id = os.environ.get("CONVERSATION_ID") or str(uuid.uuid4())
    print(f"conversation_id: {conversation_id}")

    # Two turns of one conversation. Each turn is its own trace; session.id
    # (mapped to gen_ai.conversation.id) links them.
    history: list[types.Content] = []
    for message in (f"Write a haiku about {topic}.", "Now write one about the same topic in winter."):
        with using_session(conversation_id):
            print(chat(client, history, message))
