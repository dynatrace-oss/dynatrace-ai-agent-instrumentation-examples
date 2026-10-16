import contextvars
import json
import os
import uuid

from llama_index.core.llms import ChatMessage
from llama_index.llms.azure_openai import AzureOpenAI
from openinference.instrumentation import using_session
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
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.semconv.attributes import service_attributes

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
# The app sends spans to the local collector, which forwards them to Dynatrace.
detectors = [OTELResourceDetector(), ProcessResourceDetector(), OsResourceDetector()]
resource = get_aggregated_resources(
    detectors=detectors,
    initial_resource=Resource.create({service_attributes.SERVICE_NAME: "llamaindex-openinference-demo"}),
)

SYSTEM_PROMPT = "You are a haiku poet."
TEMPERATURE = 0.7

# Request attributes the LlamaIndex instrumentor does not record: its invocation
# parameters come from LLMMetadata (no temperature), and the system prompt stays
# in gen_ai.input.messages. Set them on spans started inside an LLM call.
_request_attrs: contextvars.ContextVar[dict] = contextvars.ContextVar("request_attrs", default={})


class GenAIRequestAttributesProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        for key, value in _request_attrs.get().items():
            span.set_attribute(key, value)


tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(GenAIRequestAttributesProcessor())
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
        temperature=TEMPERATURE,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("OPENAI_API_VERSION", "2024-07-01-preview"),
    )

    # Pass CONVERSATION_ID to continue an earlier conversation; otherwise a new one starts.
    conversation_id = os.environ.get("CONVERSATION_ID") or str(uuid.uuid4())
    topic = os.environ.get("TOPIC", "observability")
    _request_attrs.set(
        {
            "gen_ai.request.temperature": TEMPERATURE,
            "gen_ai.system_instructions": json.dumps([{"type": "text", "content": SYSTEM_PROMPT}]),
        }
    )

    # Two turns of one conversation. Each llm.chat call is its own trace;
    # using_session sets session.id, which OpenInference maps to gen_ai.conversation.id.
    history = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    for prompt in (f"Write a haiku about {topic}.", "Now write another one with a hopeful tone."):
        history.append(ChatMessage(role="user", content=prompt))
        with using_session(conversation_id):
            response = llm.chat(history)
        history.append(response.message)
        print(response.message.content)
    print(f"conversation_id: {conversation_id}")
