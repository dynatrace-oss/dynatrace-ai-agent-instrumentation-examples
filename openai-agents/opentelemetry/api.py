import os

os.environ['TRACELOOP_TELEMETRY'] = "false"
os.environ['OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE'] = "delta"

def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception as e:
        print("No token was provided")
        print(e)
        return ""

token = os.environ.get("DT_API_TOKEN") or read_secret("dynatrace_otel")
headers = {"Authorization": f"Api-Token {token}"}
_dt_base = os.environ.get("DT_ENDPOINT", "https://wkf10640.live.dynatrace.com").rstrip("/")
DT_OTLP_ENDPOINT = f"{_dt_base}/api/v2/otlp"

from traceloop.sdk import Traceloop
Traceloop.init(
    app_name="openai-cs-agents",
    api_endpoint=DT_OTLP_ENDPOINT,
    disable_batch=True,
    headers=headers,
    should_enrich_metrics=True,
)

# =========================
# OpenTelemetry Logs exporter
# =========================
import logging as _logging

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

_logger_provider = LoggerProvider(
    resource=Resource.create({"service.name": "openai-cs-agents"})
)
set_logger_provider(_logger_provider)

_log_exporter = OTLPLogExporter(
    endpoint=f"{DT_OTLP_ENDPOINT}/v1/logs",
    headers=headers,
)
_logger_provider.add_log_record_processor(BatchLogRecordProcessor(_log_exporter))

_otel_log_handler = LoggingHandler(level=_logging.INFO, logger_provider=_logger_provider)
_logging.getLogger().addHandler(_otel_log_handler)


from opentelemetry import trace
tracer = trace.get_tracer("openai-agents")

# =========================
# Conversation-id propagation
# =========================
# Each chat turn arrives as its own request and therefore its own trace. To stitch
# a whole conversation back together we (1) set a stable gen_ai.conversation.id on
# the turn's root span, (2) publish it to OTel baggage in /chat so the agent/model/
# tool child spans created by the Agents SDK + Traceloop inherit it (via the span
# processor below), and (3) link each turn's trace to the previous turn's.
from opentelemetry import baggage, context as otel_context
from opentelemetry.sdk.trace import SpanProcessor as _SpanProcessor

GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"


class _ConversationIdSpanProcessor(_SpanProcessor):
    """Stamp gen_ai.conversation.id from baggage onto every span at start."""

    def on_start(self, span, parent_context=None):
        conv_id = baggage.get_baggage(GEN_AI_CONVERSATION_ID, parent_context)
        if conv_id:
            span.set_attribute(GEN_AI_CONVERSATION_ID, conv_id)

    def on_end(self, span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        return True


trace.get_tracer_provider().add_span_processor(_ConversationIdSpanProcessor())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
import time
import logging

from openai import AsyncAzureOpenAI
from agents import set_default_openai_client
openai_client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT")
)

# Set the default OpenAI client for the Agents SDK
set_default_openai_client(openai_client)

from main import (
    triage_agent,
    faq_agent,
    seat_booking_agent,
    flight_status_agent,
    cancellation_agent,
    create_initial_context,
)

from agents import (
    Runner,
    ItemHelpers,
    MessageOutputItem,
    HandoffOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    InputGuardrailTripwireTriggered,
    Handoff,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration (adjust as needed for deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Models
# =========================

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str

class MessageResponse(BaseModel):
    content: str
    agent: str

class AgentEvent(BaseModel):
    id: str
    type: str
    agent: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

class GuardrailCheck(BaseModel):
    id: str
    name: str
    input: str
    reasoning: str
    passed: bool
    timestamp: float

class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]
    agents: List[Dict[str, Any]]
    guardrails: List[GuardrailCheck] = []

# =========================
# In-memory store for conversation state
# =========================

class ConversationStore:
    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        pass

    def save(self, conversation_id: str, state: Dict[str, Any]):
        pass

class InMemoryConversationStore(ConversationStore):
    _conversations: Dict[str, Dict[str, Any]] = {}

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self._conversations.get(conversation_id)

    def save(self, conversation_id: str, state: Dict[str, Any]):
        self._conversations[conversation_id] = state

# TODO: when deploying this app in scale, switch to your own production-ready implementation
conversation_store = InMemoryConversationStore()

# =========================
# Helpers
# =========================

def _get_agent_by_name(name: str):
    """Return the agent object by name."""
    agents = {
        triage_agent.name: triage_agent,
        faq_agent.name: faq_agent,
        seat_booking_agent.name: seat_booking_agent,
        flight_status_agent.name: flight_status_agent,
        cancellation_agent.name: cancellation_agent,
    }
    return agents.get(name, triage_agent)

def _get_guardrail_name(g) -> str:
    """Extract a friendly guardrail name."""
    name_attr = getattr(g, "name", None)
    if isinstance(name_attr, str) and name_attr:
        return name_attr
    guard_fn = getattr(g, "guardrail_function", None)
    if guard_fn is not None and hasattr(guard_fn, "__name__"):
        return guard_fn.__name__.replace("_", " ").title()
    fn_name = getattr(g, "__name__", None)
    if isinstance(fn_name, str) and fn_name:
        return fn_name.replace("_", " ").title()
    return str(g)

def _build_agents_list() -> List[Dict[str, Any]]:
    """Build a list of all available agents and their metadata."""
    def make_agent_dict(agent):
        return {
            "name": agent.name,
            "description": getattr(agent, "handoff_description", ""),
            "handoffs": [getattr(h, "agent_name", getattr(h, "name", "")) for h in getattr(agent, "handoffs", [])],
            "tools": [getattr(t, "name", getattr(t, "__name__", "")) for t in getattr(agent, "tools", [])],
            "input_guardrails": [_get_guardrail_name(g) for g in getattr(agent, "input_guardrails", [])],
        }
    return [
        make_agent_dict(triage_agent),
        make_agent_dict(faq_agent),
        make_agent_dict(seat_booking_agent),
        make_agent_dict(flight_status_agent),
        make_agent_dict(cancellation_agent),
    ]

# =========================
# Main Chat Endpoint
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Main chat endpoint for agent orchestration.
    Handles conversation state, agent routing, and guardrail checks.
    """
    # Resolve the conversation identity BEFORE opening the span. Each turn is its
    # own trace, so stitching a multi-turn conversation together needs both a stable
    # conversation_id (reused across turns) and a span link back to the prior turn.
    # Honor a caller-supplied conversation_id so a client can keep one stable id
    # across turns; mint one only when the caller doesn't provide it. (Previously an
    # unknown caller id was discarded and replaced per turn, so turns never stitched.)
    conversation_id: str = req.conversation_id or uuid4().hex
    existing_state = conversation_store.get(conversation_id)
    is_new = existing_state is None

    # Link this turn's trace back to the previous turn's root span, when known.
    turn_links: List[trace.Link] = []
    if existing_state is not None:
        prev_ctx = existing_state.get("last_span_context")
        if prev_ctx is not None:
            turn_links.append(
                trace.Link(prev_ctx, attributes={"gen_ai.conversation.link": "previous_turn"})
            )

    with tracer.start_as_current_span(
        name="/chat", kind=trace.SpanKind.SERVER, links=turn_links
    ) as span:
        # gen_ai.conversation.id ties every turn of this chat together.
        span.set_attribute(GEN_AI_CONVERSATION_ID, conversation_id)

        # Initialize or retrieve conversation state
        if is_new:
            ctx = create_initial_context()
            current_agent_name = triage_agent.name
            state: Dict[str, Any] = {
                "input_items": [],
                "context": ctx,
                "current_agent": current_agent_name,
            }
            logger.info(
                "New conversation started: conversation_id=%s account_number=%s",
                conversation_id,
                ctx.account_number,
            )
            if req.message.strip() == "":
                state["last_span_context"] = span.get_span_context()
                conversation_store.save(conversation_id, state)
                return ChatResponse(
                    conversation_id=conversation_id,
                    current_agent=current_agent_name,
                    messages=[],
                    events=[],
                    context=ctx.model_dump(),
                    agents=_build_agents_list(),
                    guardrails=[],
                )
        else:
            state = existing_state

        current_agent = _get_agent_by_name(state["current_agent"])
        logger.info(
            "Handling chat message: conversation_id=%s current_agent=%s message_len=%d",
            conversation_id,
            current_agent.name,
            len(req.message),
        )
        state["input_items"].append({"content": req.message, "role": "user"})
        old_context = state["context"].model_dump().copy()
        guardrail_checks: List[GuardrailCheck] = []

        # Publish the conversation id to baggage so every child span created during
        # the agent run (model calls, tool calls, guardrails) inherits it.
        _conv_token = otel_context.attach(
            baggage.set_baggage(GEN_AI_CONVERSATION_ID, conversation_id)
        )
        try:
            result = await Runner.run(current_agent, state["input_items"], context=state["context"])
        except InputGuardrailTripwireTriggered as e:
            failed = e.guardrail_result.guardrail
            logger.warning(
                "Guardrail tripwire triggered: conversation_id=%s agent=%s guardrail=%s",
                conversation_id,
                current_agent.name,
                _get_guardrail_name(failed),
            )
            gr_output = e.guardrail_result.output.output_info
            gr_reasoning = getattr(gr_output, "reasoning", "")
            gr_input = req.message
            gr_timestamp = time.time() * 1000
            for g in current_agent.input_guardrails:
                guardrail_checks.append(GuardrailCheck(
                    id=uuid4().hex,
                    name=_get_guardrail_name(g),
                    input=gr_input,
                    reasoning=(gr_reasoning if g == failed else ""),
                    passed=(g != failed),
                    timestamp=gr_timestamp,
                ))
            refusal = "Sorry, I can only answer questions related to airline travel."
            state["input_items"].append({"role": "assistant", "content": refusal})
            return ChatResponse(
                conversation_id=conversation_id,
                current_agent=current_agent.name,
                messages=[MessageResponse(content=refusal, agent=current_agent.name)],
                events=[],
                context=state["context"].model_dump(),
                agents=_build_agents_list(),
                guardrails=guardrail_checks,
            )
        finally:
            otel_context.detach(_conv_token)

        messages: List[MessageResponse] = []
        events: List[AgentEvent] = []

        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = ItemHelpers.text_message_output(item)
                messages.append(MessageResponse(content=text, agent=item.agent.name))
                events.append(AgentEvent(id=uuid4().hex, type="message", agent=item.agent.name, content=text))
            # Handle handoff output and agent switching
            elif isinstance(item, HandoffOutputItem):
                logger.info(
                    "Agent handoff: conversation_id=%s %s -> %s",
                    conversation_id,
                    item.source_agent.name,
                    item.target_agent.name,
                )
                # Record the handoff event
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="handoff",
                        agent=item.source_agent.name,
                        content=f"{item.source_agent.name} -> {item.target_agent.name}",
                        metadata={"source_agent": item.source_agent.name, "target_agent": item.target_agent.name},
                    )
                )
                # If there is an on_handoff callback defined for this handoff, show it as a tool call
                from_agent = item.source_agent
                to_agent = item.target_agent
                # Find the Handoff object on the source agent matching the target
                ho = next(
                    (h for h in getattr(from_agent, "handoffs", [])
                     if isinstance(h, Handoff) and getattr(h, "agent_name", None) == to_agent.name),
                    None,
                )
                if ho:
                    fn = ho.on_invoke_handoff
                    fv = fn.__code__.co_freevars
                    cl = fn.__closure__ or []
                    if "on_handoff" in fv:
                        idx = fv.index("on_handoff")
                        if idx < len(cl) and cl[idx].cell_contents:
                            cb = cl[idx].cell_contents
                            cb_name = getattr(cb, "__name__", repr(cb))
                            events.append(
                                AgentEvent(
                                    id=uuid4().hex,
                                    type="tool_call",
                                    agent=to_agent.name,
                                    content=cb_name,
                                )
                            )
                current_agent = item.target_agent
            elif isinstance(item, ToolCallItem):
                tool_name = getattr(item.raw_item, "name", None)
                logger.info(
                    "Tool call: conversation_id=%s agent=%s tool=%s",
                    conversation_id,
                    item.agent.name,
                    tool_name,
                )
                raw_args = getattr(item.raw_item, "arguments", None)
                tool_args: Any = raw_args
                if isinstance(raw_args, str):
                    try:
                        import json
                        tool_args = json.loads(raw_args)
                    except Exception:
                        pass
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="tool_call",
                        agent=item.agent.name,
                        content=tool_name or "",
                        metadata={"tool_args": tool_args},
                    )
                )
                # If the tool is display_seat_map, send a special message so the UI can render the seat selector.
                if tool_name == "display_seat_map":
                    messages.append(
                        MessageResponse(
                            content="DISPLAY_SEAT_MAP",
                            agent=item.agent.name,
                        )
                    )
            elif isinstance(item, ToolCallOutputItem):
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="tool_output",
                        agent=item.agent.name,
                        content=str(item.output),
                        metadata={"tool_result": item.output},
                    )
                )

        new_context = state["context"].dict()
        changes = {k: new_context[k] for k in new_context if old_context.get(k) != new_context[k]}
        if changes:
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="context_update",
                    agent=current_agent.name,
                    content="",
                    metadata={"changes": changes},
                )
            )

        state["input_items"] = result.to_input_list()
        state["current_agent"] = current_agent.name
        # Record this turn's root span so the next turn can link back to it.
        state["last_span_context"] = span.get_span_context()
        conversation_store.save(conversation_id, state)
        logger.info(
            "Chat turn complete: conversation_id=%s current_agent=%s messages=%d events=%d",
            conversation_id,
            current_agent.name,
            len(messages),
            len(events),
        )

        # Build guardrail results: mark failures (if any), and any others as passed
        final_guardrails: List[GuardrailCheck] = []
        for g in getattr(current_agent, "input_guardrails", []):
            name = _get_guardrail_name(g)
            failed = next((gc for gc in guardrail_checks if gc.name == name), None)
            if failed:
                final_guardrails.append(failed)
            else:
                final_guardrails.append(GuardrailCheck(
                    id=uuid4().hex,
                    name=name,
                    input=req.message,
                    reasoning="",
                    passed=True,
                    timestamp=time.time() * 1000,
                ))

        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=messages,
            events=events,
            context=state["context"].dict(),
            agents=_build_agents_list(),
            guardrails=final_guardrails,
        )
