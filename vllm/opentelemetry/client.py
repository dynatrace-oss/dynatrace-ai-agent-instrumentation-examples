"""OpenAI SDK client that calls vLLM, instrumented with Traceloop.

Emits the gen_ai.* chat span that the AI Observability app shows. The OpenAI
call carries the W3C traceparent, so vLLM's own llm_request span joins the
same trace. Exports to Dynatrace when DT_ENDPOINT is set, otherwise to the
local span sink.
"""

import os
import uuid

os.environ["TRACELOOP_TELEMETRY"] = "false"
os.environ.setdefault("OTEL_SERVICE_NAME", "vllm/opentelemetry")
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

import openai
from traceloop.sdk import Traceloop
from traceloop.sdk.tracing.tracing import set_conversation_id

_dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
if _dt_base:
    endpoint = f"{_dt_base}/api/v2/otlp"
    scheme = os.environ.get("DT_AUTH_SCHEME", "Api-Token")
    headers = {"Authorization": f"{scheme} {os.environ.get('DT_API_TOKEN', '')}"}
else:
    endpoint = os.environ.get("SINK_URL", "http://localhost:14318")
    headers = {}

Traceloop.init(
    app_name=os.environ["OTEL_SERVICE_NAME"],
    api_endpoint=endpoint,
    headers=headers,
    disable_batch=True,
    should_enrich_metrics=True,
)

MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

if __name__ == "__main__":
    client = openai.OpenAI(
        base_url=os.environ.get("VLLM_URL", "http://localhost:8000") + "/v1",
        api_key="unused",
    )
    set_conversation_id(str(uuid.uuid4()))
    for _ in range(int(os.environ.get("MAX_RUNS", "1"))):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a skilled poet specializing in haiku."},
                {"role": "user", "content": "Write a haiku."},
            ],
            temperature=1,
            max_completion_tokens=64,
        )
        print(response.choices[0].message.content)
