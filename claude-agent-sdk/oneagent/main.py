import asyncio
import os
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

DEFAULT_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = (
    "You write haiku. Draft a three-line haiku about the topic, then call the "
    "count_syllables tool once with the full draft. Adjust if the counts are far "
    "from 5-7-5. Reply with only the final haiku."
)


def setup_instrumentation() -> None:
    import oneagent
    oneagent.initialize()


def _syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?-'\"")
    if not word:
        return 0
    vowels = "aeiouy"
    count, prev = 0, False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev:
            count += 1
        prev = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


@tool("count_syllables", "Count syllables per line of a draft haiku", {"text": str})
async def count_syllables(args: dict[str, Any]) -> dict[str, Any]:
    lines = [line for line in args["text"].splitlines() if line.strip()]
    counts = [sum(_syllables(w) for w in line.split()) for line in lines]
    return {"content": [{"type": "text", "text": "-".join(str(c) for c in counts)}]}


_haiku_tools = create_sdk_mcp_server(name="haiku", tools=[count_syllables])


def _options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=os.environ.get("ANTHROPIC_MODEL_ID") or DEFAULT_MODEL,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        mcp_servers={"haiku": _haiku_tools},
        allowed_tools=["mcp__haiku__count_syllables"],
        max_turns=4,
        setting_sources=[],
        # Route the bundled Claude Code CLI to Bedrock with the process's AWS credentials.
        env={
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_REGION": os.environ.get("AWS_DEFAULT_REGION") or "us-east-1",
        },
    )


async def write_haiku(topic: str) -> str:
    text = ""
    async for message in query(prompt=f"Topic: {topic}", options=_options()):
        if isinstance(message, AssistantMessage):
            parts = [b.text for b in message.content if isinstance(b, TextBlock)]
            if parts:
                text = "".join(parts)
        elif isinstance(message, ResultMessage) and message.result:
            text = message.result
    return text.strip()


def main():
    setup_instrumentation()
    print("=== Haiku Writer (Claude Agent SDK) ===\n")
    while True:
        topic = input("Topic [q to quit]: ").strip()
        if topic.lower() == "q":
            break
        print("\n" + asyncio.run(write_haiku(topic)) + "\n")


if __name__ == "__main__":
    main()
