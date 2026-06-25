import os
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from langfuse import Langfuse, observe, get_client
from langfuse.decorators import langfuse_context
from langfuse.openai import OpenAI, AzureOpenAI


def _otlp_headers() -> dict:
    raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    result = {}
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


# Initialize Langfuse to export spans via OTLP.
# public_key/secret_key must be set but are unused when a custom span_exporter is provided.
_otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
Langfuse(
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", "unused"),
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY", "unused"),
    span_exporter=OTLPSpanExporter(
        endpoint=f"{_otlp_endpoint}/v1/traces",
        headers=_otlp_headers(),
    ),
)

MODEL: str = os.environ.get("MODEL", "gpt-4o-mini")
TEMPERATURE: float = float(os.environ.get("TEMPERATURE", "0.7"))


@observe()
def generate_haiku(topic: str = "observability") -> str:
    langfuse_context.update_current_trace(
        session_id=os.environ.get("LANGFUSE_SESSION_ID", "demo-session"),
    )
    api_version = os.getenv("OPENAI_API_VERSION")
    if api_version:
        client = AzureOpenAI(
            azure_endpoint=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_version=api_version,
        )
    else:
        client = OpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": f"Write a haiku about {topic}."}],
        max_completion_tokens=50,
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    topic = os.environ.get("TOPIC", "observability")
    print(generate_haiku(topic))
    get_client().flush()
