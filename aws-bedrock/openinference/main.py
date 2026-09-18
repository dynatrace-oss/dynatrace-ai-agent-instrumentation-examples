import json
import os

import boto3

# Emit gen_ai.* attributes directly on spans (alongside llm.*/openinference.*)
# so no downstream OpenInference-to-gen_ai normalization is needed.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")


def _guardrail_config():
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID")
    if not guardrail_id:
        return None
    return {
        "guardrailIdentifier": guardrail_id,
        "guardrailVersion": os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
        "trace": "enabled",
    }


def _otlp_exporter():
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    collector_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if collector_endpoint:
        return OTLPSpanExporter(
            endpoint=collector_endpoint.rstrip("/") + "/v1/traces",
        )

    endpoint = os.environ["DT_ENDPOINT"].rstrip("/") + "/api/v2/otlp/v1/traces"
    token = os.environ["DT_API_TOKEN"]
    return OTLPSpanExporter(
        endpoint=endpoint,
        headers={"Authorization": f"Api-Token {token}"},
    )


def setup_instrumentation() -> None:
    from opentelemetry import trace as trace_api
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from openinference.instrumentation.bedrock import BedrockInstrumentor

    resource = Resource.create({SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "haiku-writer")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_otlp_exporter()))
    trace_api.set_tracer_provider(provider)
    BedrockInstrumentor().instrument(tracer_provider=provider)


_SYSTEM_PROMPT = (
    "You are a haiku poet. Write a haiku (5-7-5 syllables) about the given "
    "topic. Reply with only the haiku, no extra text."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
    return _client


def _record_guardrail_trace(span, response: dict) -> None:
    """Bedrock's Converse response carries guardrail assessment data (topic/content/
    sensitive-info policy detections) in a `trace.guardrail` block that
    openinference-instrumentation-bedrock does not read at all — it's runtime state
    the instrumentation never turns into span attributes, so there's nothing for a
    collector transform to derive it from. Set it here the same way
    pydantic-ai/opentelemetry's ask-guardrail endpoint does: the raw per-guardrail
    assessment as a JSON blob for the collector to parse into the finalized
    gen_ai.bedrock.guardrail.* attributes.
    """
    assessment = next(
        iter((response.get("trace") or {}).get("guardrail", {}).get("inputAssessment", {}).values()),
        None,
    )
    if assessment:
        span.set_attribute("gen_ai.bedrock.guardrail.input_assessment", json.dumps(assessment))


def write_haiku(topic: str) -> str:
    kwargs = {
        "modelId": os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        "system": [{"text": _SYSTEM_PROMPT}],
        "messages": [{"role": "user", "content": [{"text": f"Topic: {topic}"}]}],
    }
    gc = _guardrail_config()
    if gc:
        kwargs["guardrailConfig"] = gc
        from opentelemetry import trace as trace_api

        # openinference-instrumentation-bedrock's own Converse span has already
        # ended by the time .converse() returns (its wrapper ends the span before
        # returning control here), so attributes can't be added to it after the
        # fact. Wrap the call in our own span instead — it shares the same trace
        # as the (child) Converse span, and we control its lifecycle directly.
        tracer = trace_api.get_tracer(__name__)
        with tracer.start_as_current_span("bedrock.converse.guardrail_trace") as span:
            span.set_attribute("gen_ai.guardrail.id", gc["guardrailIdentifier"])
            span.set_attribute("gen_ai.guardrail.version", gc["guardrailVersion"])
            response = _get_client().converse(**kwargs)
            _record_guardrail_trace(span, response)
    else:
        response = _get_client().converse(**kwargs)
    content = response["output"]["message"]["content"]
    return content[0]["text"] if content else "(blocked by guardrail)"


def apply_guardrail(text: str) -> str:
    """Calls Bedrock's standalone ApplyGuardrail API directly, rather than as part
    of a Converse call. BedrockInstrumentor traces this as its own span with
    openinference.span.kind = GUARDRAIL, distinct from the LLM-kind spans write_haiku
    produces. Returns the guardrail action ("NONE" or "GUARDRAIL_INTERVENED"), or
    "SKIPPED" when no guardrail is configured.
    """
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID")
    if not guardrail_id:
        return "SKIPPED"
    response = _get_client().apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
        source="INPUT",
        content=[{"text": {"text": text}}],
    )
    return response.get("action", "NONE")


def main():
    setup_instrumentation()
    print("=== Haiku Writer ===\n")
    if _guardrail_config():
        print("Guardrail trigger:")
        print(write_haiku("football strategies for the World Cup"))
        print()
    while True:
        topic = input("Topic [q to quit]: ").strip()
        if topic.lower() == "q":
            break
        print("\n" + write_haiku(topic) + "\n")


if __name__ == "__main__":
    main()
