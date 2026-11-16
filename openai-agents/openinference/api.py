import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openinference.instrumentation import using_session
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (the Makefile points it
# at the local collector, which derives gen_ai.* metrics from the spans).
_service_name = os.environ.get("OTEL_SERVICE_NAME", "openai-agents/openinference")
_tracer_provider = trace_sdk.TracerProvider(resource=Resource.create({SERVICE_NAME: _service_name}))
_tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_tracer_provider)

# exclusive_processor replaces the Agents SDK's default exporter to the OpenAI
# tracing backend, so spans only go to OpenTelemetry.
OpenAIAgentsInstrumentor().instrument(tracer_provider=_tracer_provider, exclusive_processor=True)

import logging

from agents import (
    HandoffOutputItem,
    InputGuardrailTripwireTriggered,
    ItemHelpers,
    MessageOutputItem,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
)
from fastapi import FastAPI
from pydantic import BaseModel

from main import (
    cancellation_agent,
    create_initial_context,
    faq_agent,
    flight_status_agent,
    seat_booking_agent,
    triage_agent,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tracer = trace.get_tracer("openai-agents")
app = FastAPI()


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = ""
    # Accepts the repo-wide {"topic": "..."} request shape as well.
    topic: Optional[str] = None


class MessageResponse(BaseModel):
    content: str
    agent: str


class AgentEvent(BaseModel):
    type: str
    agent: str
    content: str


class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]


# In-memory conversation state; replace with a real store for production use.
_conversations: Dict[str, Dict[str, Any]] = {}

_agents = {
    a.name: a
    for a in (triage_agent, faq_agent, seat_booking_agent, flight_status_agent, cancellation_agent)
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    message = req.message or req.topic or ""
    conversation_id = req.conversation_id or uuid4().hex
    state = _conversations.get(conversation_id)
    if state is None:
        state = {"input_items": [], "context": create_initial_context(), "current_agent": triage_agent.name}

    # Each turn is its own trace; link it to the previous turn of the conversation.
    links = []
    if state.get("last_span_context") is not None:
        links.append(trace.Link(state["last_span_context"], attributes={"gen_ai.conversation.link": "previous_turn"}))

    with tracer.start_as_current_span("/chat", kind=trace.SpanKind.SERVER, links=links) as span:
        span.set_attribute("gen_ai.conversation.id", conversation_id)
        current_agent = _agents.get(state["current_agent"], triage_agent)
        state["input_items"].append({"content": message, "role": "user"})

        # using_session sets session.id on every span of the run; with GenAI
        # semconv enabled, OpenInference also emits it as gen_ai.conversation.id.
        with using_session(conversation_id):
            try:
                result = await Runner.run(current_agent, state["input_items"], context=state["context"])
            except InputGuardrailTripwireTriggered:
                refusal = "Sorry, I can only answer questions related to airline travel."
                state["input_items"].append({"role": "assistant", "content": refusal})
                state["last_span_context"] = span.get_span_context()
                _conversations[conversation_id] = state
                return ChatResponse(
                    conversation_id=conversation_id,
                    current_agent=current_agent.name,
                    messages=[MessageResponse(content=refusal, agent=current_agent.name)],
                    events=[AgentEvent(type="guardrail", agent=current_agent.name, content="tripwire triggered")],
                    context=state["context"].model_dump(),
                )

        messages: List[MessageResponse] = []
        events: List[AgentEvent] = []
        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = ItemHelpers.text_message_output(item)
                messages.append(MessageResponse(content=text, agent=item.agent.name))
                events.append(AgentEvent(type="message", agent=item.agent.name, content=text))
            elif isinstance(item, HandoffOutputItem):
                events.append(AgentEvent(
                    type="handoff",
                    agent=item.source_agent.name,
                    content=f"{item.source_agent.name} -> {item.target_agent.name}",
                ))
                current_agent = item.target_agent
            elif isinstance(item, ToolCallItem):
                events.append(AgentEvent(type="tool_call", agent=item.agent.name,
                                         content=getattr(item.raw_item, "name", "") or ""))
            elif isinstance(item, ToolCallOutputItem):
                events.append(AgentEvent(type="tool_output", agent=item.agent.name, content=str(item.output)))

        state["input_items"] = result.to_input_list()
        state["current_agent"] = current_agent.name
        state["last_span_context"] = span.get_span_context()
        _conversations[conversation_id] = state

        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=messages,
            events=events,
            context=state["context"].model_dump(),
        )
