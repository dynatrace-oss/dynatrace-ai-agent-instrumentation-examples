import contextvars
import json
import os
import uuid
from together import Together
from openinference.instrumentation.together import TogetherInstrumentor
from openinference.instrumentation import using_session
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, OTELResourceDetector, ProcessResourceDetector, OsResourceDetector, \
    get_aggregated_resources
from opentelemetry.semconv.attributes import service_attributes

MODEL: str = os.environ.get("MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
SYSTEM_PROMPT = "You are a haiku poet. Answer only with a haiku."
TURNS = ["Write a haiku about the sea.", "Now write one about the same sea at night."]

# System prompt of the model call in progress; read by SystemInstructionsProcessor.
_system_instructions: contextvars.ContextVar = contextvars.ContextVar("system_instructions", default=None)


class SystemInstructionsProcessor(SpanProcessor):
    """Sets gen_ai.system_instructions on spans started during a model call.

    OpenInference's GenAI semconv conversion does not emit this attribute, so
    the app sets it in the OTel GenAI format (JSON array of parts).
    """

    def on_start(self, span, parent_context=None):
        if (instructions := _system_instructions.get()) is not None:
            span.set_attribute("gen_ai.system_instructions",
                               json.dumps([{"type": "text", "content": instructions}]))

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(detectors=detectors, initial_resource=Resource.create(
    {service_attributes.SERVICE_NAME: "openinference"}))

tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(SystemInstructionsProcessor())
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

TogetherInstrumentor().instrument(tracer_provider=tracer_provider)


def chat(client: Together, history: list, conversation_id: str) -> str:
    """Runs one conversation turn; session.id becomes gen_ai.conversation.id."""
    with using_session(conversation_id):
        token = _system_instructions.set(SYSTEM_PROMPT)
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history],
                max_tokens=2000,
                temperature=0.7,
            )
        finally:
            _system_instructions.reset(token)
    return response.choices[0].message.content


if __name__ == "__main__":
    # TOGETHER_BASE_URL is read automatically by the Together AI client when set (e.g. by the e2e mock).
    client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
    # Reuse CONVERSATION_ID to continue a conversation; a new one is generated when unset.
    conversation_id = os.getenv("CONVERSATION_ID") or str(uuid.uuid4())
    print(f"conversation_id: {conversation_id}")
    history: list = []
    for turn in TURNS:
        history.append({"role": "user", "content": turn})
        answer = chat(client, history, conversation_id)
        history.append({"role": "assistant", "content": answer})
        print(answer)
