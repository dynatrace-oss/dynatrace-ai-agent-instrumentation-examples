import os

from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

_web_app_info = None


def setup_instrumentation() -> None:
    global _web_app_info
    import oneagent
    oneagent.initialize()
    sdk = oneagent.get_sdk()
    _web_app_info = sdk.create_web_application_info(
        virtual_host="localhost",
        application_id=os.environ.get("OTEL_SERVICE_NAME", "aws-bedrock/oneagent"),
        context_root="/",
    )


_chain = None


def _get_chain():
    global _chain
    if _chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a haiku poet. Write a haiku (5-7-5 syllables) about the given topic. Reply with only the haiku, no extra text."),
            ("human", "Topic: {topic}"),
        ])
        model = ChatBedrock(
            model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
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
