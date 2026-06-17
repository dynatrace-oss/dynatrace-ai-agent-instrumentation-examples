import os

from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


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
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from openinference.instrumentation.bedrock import BedrockInstrumentor

    resource = Resource({SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "haiku-writer")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_otlp_exporter()))
    trace_api.set_tracer_provider(provider)
    LangChainInstrumentor().instrument(tracer_provider=provider)
    BedrockInstrumentor().instrument(tracer_provider=provider)


_chain = None


def _get_chain():
    global _chain
    if _chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a haiku poet. Write a haiku (5-7-5 syllables) about the given topic. Reply with only the haiku, no extra text."),
            ("human", "Topic: {topic}"),
        ])
        model = ChatBedrock(
            model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            provider="anthropic",
        )
        _chain = prompt | model | StrOutputParser()
    return _chain


def write_haiku(topic: str) -> str:
    return _get_chain().invoke({"topic": topic})


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
