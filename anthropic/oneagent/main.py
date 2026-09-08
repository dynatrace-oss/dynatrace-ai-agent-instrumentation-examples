import os

import anthropic

from style_guide import HAIKU_STYLE_GUIDE


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
        model=os.environ.get("ANTHROPIC_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        max_tokens=256,
        # HAIKU_STYLE_GUIDE is a fixed reference block (style rules + kigo almanac) rather
        # than a one-line instruction: Bedrock only creates a cache checkpoint once the
        # cached prefix clears a per-model minimum token count (4,096 tokens for
        # claude-haiku-4-5), and a short instruction never gets close. Keeping the block
        # byte-identical across calls is what lets repeated requests hit the cache.
        system=[
            {
                "type": "text",
                "text": HAIKU_STYLE_GUIDE,
                "cache_control": {"type": "ephemeral"},
            }
        ],
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
