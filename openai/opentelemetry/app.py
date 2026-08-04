import os
import uuid
import openai
from openai import Stream
from openai.types.chat import ChatCompletionChunk

os.environ["TRACELOOP_TELEMETRY"] = "false"
os.environ.setdefault("OTEL_SERVICE_NAME", "openai")
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

from traceloop.sdk import Traceloop
from traceloop.sdk.tracing.tracing import set_conversation_id

_app_name = os.environ.get("OTEL_SERVICE_NAME", "openai")
_dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
_dt_token = os.environ.get("DT_API_TOKEN", "")
Traceloop.init(
    app_name=_app_name,
    api_endpoint=f"{_dt_base}/api/v2/otlp",
    headers={"Authorization": f"Api-Token {_dt_token}"},
    disable_batch=True,
    should_enrich_metrics=True,
)

MODEL: str = os.environ.get("MODEL", "gpt-4o")

if __name__ == "__main__":
    api_version = os.getenv("OPENAI_API_VERSION")
    if api_version:
        client = openai.AzureOpenAI(
            azure_endpoint=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_version=api_version,
        )
    else:
        client = openai.OpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    set_conversation_id(str(uuid.uuid4()))
    response: Stream[ChatCompletionChunk] = client.chat.completions.create(  # type: ignore[assignment]
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a skilled poet specializing in haiku."},
            {"role": "user", "content": "Write a haiku."},
        ],
        temperature=1,
        max_completion_tokens=2000,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in response:
        if chunk.choices and (content := chunk.choices[0].delta.content):
            print(content, end="")
