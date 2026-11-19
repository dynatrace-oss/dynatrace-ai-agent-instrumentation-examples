"""App-side emission of the GenAI agent call-count metrics.

`gen_ai.invoke_agent.inference_calls` and `gen_ai.invoke_agent.tool_calls` are
Histograms of the number of calls made *during a single agent invocation*
(https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md).

That per-invocation shape is why they cannot be derived at the collector the way
the duration metrics are: a span-to-metrics connector counting `chat` /
`execute_tool` spans produces a running total, not a distribution over
invocations. The count has to be closed out where the invocation is, so it is
recorded here via Microsoft Agent Framework middleware.

Microsoft Agent Framework does not emit these two metrics itself as of 1.13.0.
"""

from contextvars import ContextVar

from agent_framework import agent_middleware, chat_middleware, function_middleware
from opentelemetry import metrics as otel_metrics

_meter = otel_metrics.get_meter("dynatrace.genai.agent.metrics")

# Explicit buckets: these count calls, not seconds, so the SDK's default
# latency-shaped boundaries would put every realistic value in the first bucket.
_inference_calls = _meter.create_histogram(
    name="gen_ai.invoke_agent.inference_calls",
    unit="{inference_call}",
    description="The number of inference (model) calls a GenAI agent makes during a single invocation",
    explicit_bucket_boundaries_advisory=[0, 1, 2, 3, 5, 8, 13, 21],
)

_tool_calls = _meter.create_histogram(
    name="gen_ai.invoke_agent.tool_calls",
    unit="{tool_call}",
    description="The number of tool calls a GenAI agent makes during a single invocation",
    explicit_bucket_boundaries_advisory=[0, 1, 2, 3, 5, 8, 13, 21],
)

# Holds the counters for the agent invocation currently on the stack. A dict is
# used rather than two ints so that the chat/function middleware mutate the same
# object the agent middleware will read: the framework may run tool calls in
# child tasks, and a child task inherits a *copy* of the context, so rebinding
# the ContextVar there would be invisible to the parent. Mutating the shared dict
# is not.
_call_counts: ContextVar[dict[str, int] | None] = ContextVar("genai_call_counts", default=None)


@agent_middleware
async def record_invocation_call_counts(context, next) -> None:
    """Open a counting scope for one agent invocation and record it on close."""
    counts = {"inference": 0, "tool": 0}
    token = _call_counts.set(counts)
    try:
        await next()
    finally:
        _call_counts.reset(token)

        agent = getattr(context, "agent", None)
        agent_name = getattr(agent, "name", None) or getattr(agent, "id", None)
        attributes = {"gen_ai.operation.name": "invoke_agent"}
        if agent_name:
            attributes["gen_ai.agent.name"] = agent_name

        # Recorded in the `finally` so a failed invocation still reports the calls
        # it made before failing — those are exactly the ones worth seeing.
        _inference_calls.record(counts["inference"], attributes)
        _tool_calls.record(counts["tool"], attributes)


@chat_middleware
async def count_inference_call(context, next) -> None:
    """Count one model call against the enclosing agent invocation."""
    counts = _call_counts.get()
    if counts is not None:
        counts["inference"] += 1
    await next()


@function_middleware
async def count_tool_call(context, next) -> None:
    """Count one tool call against the enclosing agent invocation."""
    counts = _call_counts.get()
    if counts is not None:
        counts["tool"] += 1
    await next()


# Attach to every Agent in the demo. A chat or function call made outside an
# agent invocation finds no counting scope and is simply not counted, which
# matches the metric's per-invocation definition.
CALL_COUNT_MIDDLEWARE = [
    record_invocation_call_counts,
    count_inference_call,
    count_tool_call,
]
