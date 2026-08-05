"""
PoC: caller-side OpenTelemetry instrumentation for Amazon Bedrock AgentCore's
fully-managed harness (`invoke_harness`).

Unlike aws-bedrock-agents/oneagent (a self-hosted LangGraph agent deployed
*into* AgentCore Runtime, where OneAgent auto-instruments the agent's own
Bedrock calls from the inside), this demo represents a caller that does NOT
own the harness's execution: it only has a `harnessArn` and the boto3
`bedrock-agentcore` client. There is nothing to install OneAgent into on the
harness side, so the caller manually creates a `gen_ai.*`-conventioned OTel
span (and matching OTel metrics) around the `invoke_harness` call itself.
"""

import os
import time
import uuid

import boto3
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import Counter, Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

MOCK_AGENTCORE = os.getenv("MOCK_AGENTCORE", "false").lower() == "true"
GEN_AI_PROVIDER = "aws.bedrock_agentcore"

_tracer = None
_meter = None
_token_usage_counter = None
_operation_duration_histogram = None
_harness_client = None


def setup_instrumentation():
    """Wires up an OTLP/HTTP trace + metric pipeline pointed at Dynatrace.

    Dynatrace's OTLP metric ingest only accepts delta temporality, so the
    metric reader is configured accordingly -- otherwise cumulative sums get
    rejected with HTTP 400 (same gotcha the aws-bedrock/opentelemetry demo
    documents).
    """
    global _tracer, _meter, _token_usage_counter, _operation_duration_histogram

    service_name = os.getenv("OTEL_SERVICE_NAME", "aws-bedrock-agentcore-example")
    resource = Resource.create({"service.name": service_name})

    trace_exporter = OTLPSpanExporter(
        endpoint=os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"],
        headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_exporter = OTLPMetricExporter(
        endpoint=os.environ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"],
        headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
        preferred_temporality={
            # Counter/Histogram -> delta, as required by Dynatrace's OTLP ingest.
            Counter: AggregationTemporality.DELTA,
            Histogram: AggregationTemporality.DELTA,
        },
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)],
    )
    metrics.set_meter_provider(meter_provider)

    _tracer = trace.get_tracer(__name__)
    _meter = metrics.get_meter(__name__)
    # These two metric names/shapes intentionally mirror gen_ai.client.token.usage /
    # gen_ai.client.operation.duration, which is what the AI Observability app's
    # cost and latency charts read. Setting span attributes alone is not enough:
    # the app's PPX pipeline only *derives* these metrics from spans for
    # OneAgent-sourced telemetry -- for OTel-sourced telemetry (this demo), the
    # app expects the metrics to be emitted directly, the same way the
    # Traceloop-based aws-bedrock/opentelemetry demo does it.
    _token_usage_counter = _meter.create_counter(
        "gen_ai.client.token.usage", unit="{token}", description="Number of tokens used in GenAI operations"
    )
    _operation_duration_histogram = _meter.create_histogram(
        "gen_ai.client.operation.duration", unit="s", description="GenAI operation duration"
    )


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
    """
    text = f"(mock harness response to: {prompt!r})"
    yield {"messageStart": {"role": "assistant"}}
    yield {"contentBlockStart": {"contentBlockIndex": 0}}
    yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": text}}}
    yield {"contentBlockStop": {"contentBlockIndex": 0}}
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
        span.set_attribute("aws.bedrock_agentcore.harness_arn", harness_arn)

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
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                )
                stream = response["stream"]

            text_parts = []
            usage = {}
            latency_ms = None
            stop_reason = None

            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "text" in delta:
                        text_parts.append(delta["text"])
                elif "messageStop" in event:
                    stop_reason = event["messageStop"].get("stopReason")
                elif "metadata" in event:
                    meta = event["metadata"]
                    usage = meta.get("usage", {}) or {}
                    latency_ms = (meta.get("metrics", {}) or {}).get("latencyMs")

            duration_s = time.monotonic() - start
            input_tokens = usage.get("inputTokens")
            output_tokens = usage.get("outputTokens")

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
                "text": "".join(text_parts),
                "usage": usage,
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
