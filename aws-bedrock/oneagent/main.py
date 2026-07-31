import os

import boto3


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


def write_haiku(topic: str) -> str:
    kwargs = {
        "modelId": os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        "system": [{"text": _SYSTEM_PROMPT}],
        "messages": [{"role": "user", "content": [{"text": f"Topic: {topic}"}]}],
    }
    gc = _guardrail_config()
    if gc:
        kwargs["guardrailConfig"] = gc
    response = _get_client().converse(**kwargs)
    content = response["output"]["message"]["content"]
    return content[0]["text"] if content else "(blocked by guardrail)"


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
