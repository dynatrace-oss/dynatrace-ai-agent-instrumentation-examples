"""OpenAI SDK client that calls vLLM, instrumented with OpenInference.

Emits the gen_ai.* chat span that the AI Observability app shows. An httpx
hook injects the W3C traceparent of that span into each request, so vLLM's
own llm_request span joins the same trace. Exports to Dynatrace when
DT_ENDPOINT is set, otherwise to the local span sink.
"""

import os
import uuid

os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

import httpx
import openai
from openinference.instrumentation import using_attributes
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

_dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
if _dt_base:
    endpoint = f"{_dt_base}/api/v2/otlp/v1/traces"
    scheme = os.environ.get("DT_AUTH_SCHEME", "Api-Token")
    headers = {"Authorization": f"{scheme} {os.environ.get('DT_API_TOKEN', '')}"}
else:
    endpoint = os.environ.get("SINK_URL", "http://localhost:14318") + "/v1/traces"
    headers = {}

# Client spans are never sampled: the app's token and cost views need all of them.
tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "vllm/opentelemetry")})
)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers)))
trace.set_tracer_provider(tracer_provider)
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-0.5B-Instruct")


def _inject_traceparent(request: httpx.Request) -> None:
    propagate.inject(request.headers)


if __name__ == "__main__":
    client = openai.OpenAI(
        base_url=os.environ.get("VLLM_URL", "http://localhost:8000") + "/v1",
        api_key="unused",
        http_client=httpx.Client(event_hooks={"request": [_inject_traceparent]}),
    )
    with using_attributes(session_id=str(uuid.uuid4())):
        for _ in range(int(os.environ.get("MAX_RUNS", "1"))):
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a skilled poet specializing in haiku."},
                    {"role": "user", "content": "Write a haiku."},
                ],
                temperature=1,
                max_completion_tokens=32,
            )
            print(response.choices[0].message.content)
    tracer_provider.shutdown()
