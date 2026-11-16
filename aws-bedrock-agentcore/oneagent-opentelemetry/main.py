"""
PoC: caller-side OpenTelemetry instrumentation for Amazon Bedrock AgentCore's
fully-managed harness (`invoke_harness`).

Unlike aws-bedrock-agents/oneagent (a self-hosted LangGraph agent deployed
*into* AgentCore Runtime, where OneAgent auto-instruments the agent's own
Bedrock calls from the inside), this demo represents a caller that does NOT
own the harness's execution: it only has a `harnessArn` and the boto3
`bedrock-agentcore` client. There is nothing to install OneAgent into on the
harness side, so the caller manually creates a `gen_ai.*`-conventioned span
(and matching metrics) around the `invoke_harness` call itself.

Traces and metrics are deliberately handled differently here:

- The SPAN is created via the plain OpenTelemetry *API* only -- no SDK, no
  exporter, no TracerProvider. With OneAgent's "OpenTelemetry (Python)"
  opt-in enabled (see README), OneAgent intercepts start_as_current_span()
  calls directly and correlates the resulting span into its own PurePath, as
  a real child of the incoming HTTP request. Configuring this app's own SDK
  TracerProvider/exporter on top of that (an earlier version of this PoC
  did) does not get replaced or blocked by OneAgent -- it runs in parallel,
  producing a second, disconnected copy of the same span via a separate
  pipeline (proven empirically -- see the README). Using only the API here
  avoids that duplication.
- The METRICS (gen_ai.client.token.usage / gen_ai.client.operation.duration)
  ARE exported via a real SDK MeterProvider + OTLP exporter (see
  setup_metrics_instrumentation() below), unlike the span. Confirmed
  empirically (see README): PPX's span-derived metric extraction, which
  covers this same pair of metrics for OneAgent-sourced *spans* (and would
  have made a self-exported copy here genuinely redundant/double-counted),
  is not actually producing data for this span on the tested tenant --
  waited 24+ minutes with zero datapoints. Exporting metrics directly is the
  only way to get them, and does not carry the same duplication risk the
  span did, because nothing else is currently producing them.
"""

import json
import os
import time
import uuid

import boto3
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import Counter, Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, Status, StatusCode

MOCK_AGENTCORE = os.getenv("MOCK_AGENTCORE", "false").lower() == "true"
GEN_AI_PROVIDER = "aws.bedrock_agentcore"
# Matches the model already validated elsewhere in this repo (aws-bedrock/*).
# Passed as a per-invocation override so the caller genuinely knows the
# requested model -- InvokeHarness's response never reports which model the
# harness actually used, so gen_ai.request.model can only be set from what we
# asked for, not confirmed from the response. gen_ai.response.model is left
# unset for that reason; see the README's "known gaps" section.
DEFAULT_MODEL_ID = os.getenv("HARNESS_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

_harness_client = None

# opentelemetry-api's get_tracer() is always safe to call -- with no
# TracerProvider configured (this app never calls set_tracer_provider()), it
# returns a no-op proxy by default. OneAgent's Python OpenTelemetry support
# intercepts the start_as_current_span() call itself, so it captures real
# span data as long as OneAgent is present with that feature enabled,
# regardless of whether this proxy is backed by a real SDK.
_tracer = trace.get_tracer(__name__)
_meter = None
_token_usage_counter = None
_operation_duration_histogram = None


def setup_metrics_instrumentation():
    """Wires up a real OTLP/HTTP *metrics* pipeline pointed at Dynatrace.

    Deliberately metrics-only -- see the module docstring for why the span
    stays on the plain API with no exporter. Dynatrace's OTLP metric ingest
    only accepts delta temporality, so the reader is configured accordingly
    -- otherwise cumulative sums get rejected with HTTP 400 (same gotcha the
    aws-bedrock/opentelemetry demo documents).
    """
    global _meter, _token_usage_counter, _operation_duration_histogram

    service_name = os.getenv("OTEL_SERVICE_NAME", "aws-bedrock-agentcore-example")
    resource = Resource.create({"service.name": service_name})

    metric_exporter = OTLPMetricExporter(
        endpoint=os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"],
        headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
        preferred_temporality={
            Counter: AggregationTemporality.DELTA,
            Histogram: AggregationTemporality.DELTA,
        },
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)],
    )
    metrics.set_meter_provider(meter_provider)

    _meter = metrics.get_meter(__name__)
    # These mirror gen_ai.client.token.usage / gen_ai.client.operation.duration,
    # the metrics the AI Observability app's cost/latency charts read.
    _token_usage_counter = _meter.create_counter(
        "gen_ai.client.token.usage", unit="{token}", description="Number of tokens used in GenAI operations"
    )
    _operation_duration_histogram = _meter.create_histogram(
        "gen_ai.client.operation.duration", unit="s", description="GenAI operation duration"
    )


def _messages(role: str, text: str) -> str:
    # Matches the message-form shape used elsewhere in this repo
    # (aws-bedrock/opentelemetry's _stamp_turn_io()) for gen_ai.input.messages /
    # gen_ai.output.messages -- only the message form is set (not the flat
    # gen_ai.prompt.N/completion.0 form), since the Prompts view renders both
    # if both are present, duplicating the same turn.
    return json.dumps([{"role": role, "parts": [{"type": "text", "content": text}]}])


def _get_harness_client():
    global _harness_client
    if _harness_client is None:
        _harness_client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _harness_client


def _mock_stream(prompt: str):
    """Fakes the shape of a real InvokeHarness streaming response so this
    demo's instrumentation path can be exercised without AWS credentials or a
    deployed harness. Event names/fields match the botocore bedrock-agentcore
    2024-02-28 service model (InvokeHarnessStreamOutput / HarnessMetadataEvent).

    Simulates two agent-loop iterations (e.g. a tool call followed by the
    final answer), each with its own metadata event -- the schema does not
    guarantee a single metadata event per invocation (the harness supports
    maxIterations), so this exercises the multi-metadata accumulation path in
    invoke_harness() rather than only the single-iteration case.
    """
    text = f"(mock harness response to: {prompt!r})"
    yield {"messageStart": {"role": "assistant"}}

    # Iteration 1: a simulated tool call.
    yield {"contentBlockStart": {"contentBlockIndex": 0}}
    yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "(mock tool call)"}}}
    yield {"contentBlockStop": {"contentBlockIndex": 0}}
    yield {"metadata": {"usage": {"inputTokens": 30, "outputTokens": 8, "totalTokens": 38}, "metrics": {"latencyMs": 400}}}

    # Iteration 2: the final answer.
    yield {"contentBlockStart": {"contentBlockIndex": 1}}
    yield {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"text": text}}}
    yield {"contentBlockStop": {"contentBlockIndex": 1}}
    yield {"messageStop": {"stopReason": "end_turn"}}
    yield {
        "metadata": {
            "usage": {"inputTokens": 42, "outputTokens": 17, "totalTokens": 59},
            "metrics": {"latencyMs": 850},
        }
    }


def invoke_harness(prompt: str, session_id: str) -> dict:
    """Calls Bedrock AgentCore's `invoke_harness` wrapped in a manually
    created gen_ai span + metrics, since there is no OneAgent (or other
    auto-instrumentation) running inside the managed harness itself.
    """
    harness_arn = os.environ.get("HARNESS_ARN", "arn:aws:bedrock-agentcore:us-east-1:000000000000:harness/mock-harness-0000000000")

    with _tracer.start_as_current_span("invoke_harness", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.provider.name", GEN_AI_PROVIDER)
        span.set_attribute("gen_ai.agent.name", harness_arn.split("/")[-1])
        span.set_attribute("gen_ai.conversation.id", session_id)
        span.set_attribute("gen_ai.request.model", DEFAULT_MODEL_ID)
        span.set_attribute("aws.bedrock_agentcore.harness_arn", harness_arn)
        span.set_attribute("gen_ai.input.messages", _messages("user", prompt))

        # InvokeHarness accepts W3C trace-context fields as first-class
        # request parameters (they map to the traceparent/tracestate/baggage
        # headers AWS documents for AgentCore observability) -- no boto3
        # event-hook header injection needed, unlike the AgentCore Runtime
        # (invoke_agent_runtime) sample AWS publishes.
        span_ctx = span.get_span_context()
        trace_parent = f"00-{span_ctx.trace_id:032x}-{span_ctx.span_id:016x}-{span_ctx.trace_flags:02x}"

        start = time.monotonic()
        try:
            if MOCK_AGENTCORE:
                stream = _mock_stream(prompt)
            else:
                client = _get_harness_client()
                response = client.invoke_harness(
                    harnessArn=harness_arn,
                    runtimeSessionId=session_id,
                    traceParent=trace_parent,
                    model={"bedrockModelConfig": {"modelId": DEFAULT_MODEL_ID}},
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                )
                stream = response["stream"]

            text_parts = []
            input_tokens = None
            output_tokens = None
            latency_ms_total = None
            metadata_event_count = 0
            stop_reason = None

            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "text" in delta:
                        text_parts.append(delta["text"])
                elif "messageStop" in event:
                    stop_reason = event["messageStop"].get("stopReason")
                elif "metadata" in event:
                    # The harness runs an internal agent loop (maxIterations),
                    # and the schema does not guarantee a single metadata event
                    # per invocation -- accumulate rather than overwrite, so a
                    # multi-iteration call reports total usage, not just
                    # whichever iteration's event happened to arrive last.
                    metadata_event_count += 1
                    meta = event["metadata"]
                    event_usage = meta.get("usage", {}) or {}
                    event_metrics = meta.get("metrics", {}) or {}
                    if event_usage.get("inputTokens") is not None:
                        input_tokens = (input_tokens or 0) + event_usage["inputTokens"]
                    if event_usage.get("outputTokens") is not None:
                        output_tokens = (output_tokens or 0) + event_usage["outputTokens"]
                    if event_metrics.get("latencyMs") is not None:
                        latency_ms_total = (latency_ms_total or 0) + event_metrics["latencyMs"]

            duration_s = time.monotonic() - start
            latency_ms = latency_ms_total
            response_text = "".join(text_parts)
            if metadata_event_count > 1:
                span.set_attribute("aws.bedrock_agentcore.metadata_event_count", metadata_event_count)

            span.set_attribute("gen_ai.output.messages", _messages("assistant", response_text))
            if input_tokens is not None:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            if output_tokens is not None:
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            if stop_reason:
                span.set_attribute("gen_ai.response.finish_reasons", [stop_reason])
            if latency_ms is not None:
                span.set_attribute("aws.bedrock_agentcore.harness_latency_ms", latency_ms)

            metric_attrs = {"gen_ai.provider.name": GEN_AI_PROVIDER, "gen_ai.operation.name": "invoke_agent"}
            if input_tokens is not None:
                _token_usage_counter.add(input_tokens, {**metric_attrs, "gen_ai.token.type": "input"})
            if output_tokens is not None:
                _token_usage_counter.add(output_tokens, {**metric_attrs, "gen_ai.token.type": "output"})
            _operation_duration_histogram.record(duration_s, metric_attrs)

            span.set_status(Status(StatusCode.OK))
            return {
                "text": response_text,
                "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
                "harness_latency_ms": latency_ms,
                "stop_reason": stop_reason,
                "trace_id": format(span_ctx.trace_id, "032x"),
            }
        except Exception as exc:  # noqa: BLE001 - reported on the span, then re-raised
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def run_orchestrator(prompt: str) -> dict:
    """Entry point called by the FastAPI handler. Each HTTP request gets its
    own AgentCore runtime session id.
    """
    session_id = str(uuid.uuid4())
    return invoke_harness(prompt, session_id)
