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
    from openinference.instrumentation.cohere import CohereInstrumentor

    resource = Resource.create({SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "cohere-haiku-writer")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_otlp_exporter()))
    trace_api.set_tracer_provider(provider)
    CohereInstrumentor().instrument(tracer_provider=provider)


_SYSTEM_PROMPT = (
    "You are a haiku poet. Write a haiku (5-7-5 syllables) about the given "
    "topic. Reply with only the haiku, no extra text."
)

MODEL: str = os.environ.get("MODEL", "command-r-08-2024")

_client = None


def _get_client():
    global _client
    if _client is None:
        import cohere

        _client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
    return _client


def write_haiku(topic: str) -> str:
    response = _get_client().chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Topic: {topic}"},
        ],
        temperature=1.0,
        max_tokens=2000,
    )
    return response.message.content[0].text


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
