import os

import anthropic


def setup_instrumentation() -> None:
    import oneagent
    oneagent.initialize()


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.AnthropicBedrock(
            aws_region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
    return _client


def write_haiku(topic: str) -> str:
    message = _get_client().messages.create(
        model=os.environ.get("ANTHROPIC_MODEL_ID", "anthropic.claude-haiku-4-5-20251001:0"),
        max_tokens=256,
        system="You are a haiku poet. Write a haiku (5-7-5 syllables) about the given topic. Reply with only the haiku, no extra text.",
        messages=[{"role": "user", "content": f"Topic: {topic}"}],
    )
    return message.content[0].text


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
