import os

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

SYSTEM_PROMPT = (
    "You are a skilled poet specializing in haiku. "
    "Reply with a haiku only (3 lines, 5-7-5 syllables)."
)


def setup_instrumentation() -> None:
    import oneagent
    oneagent.initialize()


def _models() -> list[BaseChatModel]:
    # Gemini always runs (GOOGLE_API_KEY). Claude runs only when ANTHROPIC_API_KEY is set.
    models: list[BaseChatModel] = [
        ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
    ]
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        models.append(ChatAnthropic(model=os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")))
    return models


def write_haiku(topic: str) -> str:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Write a haiku about {topic}."),
    ]
    haikus = [str(model.invoke(messages).content) for model in _models()]
    return "\n\n".join(haikus)


def main():
    setup_instrumentation()
    print("=== Haiku Writer (LangChain + OneAgent) ===\n")
    while True:
        topic = input("Topic [q to quit]: ").strip()
        if topic.lower() == "q":
            break
        print("\n" + write_haiku(topic) + "\n")


if __name__ == "__main__":
    main()
