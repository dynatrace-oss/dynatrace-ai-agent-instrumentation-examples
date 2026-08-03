"""Tracing setup for the fixtures app.

Two things here that a plain Traceloop app does not need (both verified against
langchain-core 1.5.3 / traceloop-sdk 0.62.1, see SPEC.md §3.6):

1. LangChain must be instrumented **explicitly**. `Traceloop.init()` does not
   auto-instrument it when only `langchain-core` (no `langchain` meta-package)
   is installed, so a plain `model.invoke()` emits zero spans without this.

2. `gen_ai.conversation.id` is set by us via a SpanProcessor reading a
   contextvar. The native `config.configurable.thread_id` mapping only fires in
   the LangGraph path, not for a plain chat-model invoke.
"""

import os

# Must be set before traceloop / the instrumentation is imported.
os.environ["TRACELOOP_TELEMETRY"] = "false"
# Dynatrace ingests delta metrics only; export delta temporality from the SDK.
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
# Capture message content as gen_ai.input.messages / gen_ai.output.messages
# (off by default in the GenAI semconv).
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

import contextvars

from opentelemetry import trace
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.sdk.trace import SpanProcessor
from traceloop.sdk import Traceloop

GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
# Grounding context / source text (RAG). The OTel GenAI semconv has no standard
# attribute for this, and dt-evals ships no default context field — so this is a
# contract: the dt-evals config must map spanFields.context to this attribute.
GEN_AI_CONTEXT = "gen_ai.context"
GEN_AI_REFERENCE = "gen_ai.reference"

_span_attrs: contextvars.ContextVar = contextvars.ContextVar(
    "fixture_span_attrs", default=None
)

_initialized = False


class FixtureSpanProcessor(SpanProcessor):
    """Stamp fixture-driven attributes (conversation id, grounding context,
    reference) onto every span started while a case is active. The native OTel
    GenAI path emits none of these for a plain chat invoke, so we add them here
    from a contextvar (SPEC.md §3.5/§3.6)."""

    def on_start(self, span, parent_context=None):
        attrs = _span_attrs.get()
        if not attrs:
            return
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, value)

    def on_end(self, span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def set_span_attributes(attrs: dict):
    """Mark the fixture attributes for spans started in this context."""
    return _span_attrs.set(attrs)


def reset_span_attributes(token) -> None:
    _span_attrs.reset(token)


def init_tracing(service_name: str, *, exporter=None, api_endpoint=None, headers=None) -> None:
    """Initialize Traceloop, instrument LangChain, and install the conversation
    processor.

    Pass `exporter` for tests (in-memory, no tenant); pass `api_endpoint` +
    `headers` to ship straight to a Dynatrace tenant.

    Idempotent: the first call wins (Traceloop can only be initialized once), so
    a test can set up an in-memory exporter before the app's startup runs.
    """
    global _initialized
    if _initialized:
        return

    kwargs = {"app_name": service_name, "disable_batch": True}
    if exporter is not None:
        kwargs["exporter"] = exporter
    else:
        kwargs["api_endpoint"] = api_endpoint
        kwargs["headers"] = headers
        kwargs["should_enrich_metrics"] = True
    Traceloop.init(**kwargs)

    if not LangchainInstrumentor().is_instrumented_by_opentelemetry:
        LangchainInstrumentor().instrument()

    trace.get_tracer_provider().add_span_processor(FixtureSpanProcessor())
    _initialized = True
