import os


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
    from openinference.instrumentation.ollama import OllamaInstrumentor

    resource = Resource.create({SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "ollama-haiku-writer")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_otlp_exporter()))
    trace_api.set_tracer_provider(provider)
    OllamaInstrumentor().instrument(tracer_provider=provider)


_SYSTEM_PROMPT = (
    "You are a haiku poet. Write a haiku (5-7-5 syllables) about the given "
    "topic. Reply with only the haiku, no extra text."
)

MODEL: str = os.environ.get("MODEL", "llama3.2")
OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

_client = None


def _get_client():
    global _client
    if _client is None:
        from ollama import Client

        _client = Client(host=OLLAMA_HOST)
    return _client


def write_haiku(topic: str) -> str:
    response = _get_client().chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Topic: {topic}"},
        ],
        options={"temperature": 1.0, "num_predict": 2000},
    )
    return response.message.content


def main():
    setup_instrumentation()
    print("=== Haiku Writer ===\n")
    while True:
        topic = input("Topic [q to quit]: ").strip()
        if topic.lower() == "q":
            break
        print("\n" + write_haiku(topic) + "\n")


if __name__ == "__main__":
    main()
