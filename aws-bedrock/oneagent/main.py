import os

from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def _guardrail_config():
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID")
    if not guardrail_id:
        return None
    return {
        "guardrailIdentifier": guardrail_id,
        "guardrailVersion": os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
        "trace": "enabled",
    }


def setup_instrumentation() -> None:
    import oneagent
    oneagent.initialize()


_chain = None


def _get_chain():
    global _chain
    if _chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a haiku poet. Write a haiku (5-7-5 syllables) about the given topic. Reply with only the haiku, no extra text."),
            ("human", "Topic: {topic}"),
        ])
        kwargs = {
            "model_id": os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
            "region_name": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "provider": "anthropic",
        }
        gc = _guardrail_config()
        if gc:
            kwargs["guardrails"] = gc
        model = ChatBedrock(**kwargs)
        _chain = prompt | model | StrOutputParser()
    return _chain


def write_haiku(topic: str) -> str:
    return _get_chain().invoke({"topic": topic})


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
