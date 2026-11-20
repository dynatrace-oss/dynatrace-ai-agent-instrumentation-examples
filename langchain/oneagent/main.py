import os

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import chain
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

SYSTEM_PROMPT = (
    "You are a skilled poet specializing in haiku. "
    "Always look up the haiku guide with the search_haiku_guide tool first, "
    "then reply with a haiku only (3 lines, 5-7-5 syllables)."
)

# A small "haiku guide" the model retrieves from through the search_haiku_guide tool.
GUIDE = [
    "Spring kigo (seasonal words): cherry blossoms, plum rain, young leaves, melting snow, swallows returning.",
    "Summer kigo (seasonal words): cicadas, fireflies, thunderstorms, morning glories, green rice fields.",
    "Autumn kigo (seasonal words): harvest moon, falling leaves, migrating geese, chrysanthemums, crisp wind.",
    "Winter kigo (seasonal words): first frost, bare branches, snowfall, long nights, breath turning to mist.",
    "The 5-7-5 rule: a haiku has three lines of five, seven and five syllables. Count syllables, not words.",
    "Kireji (cutting word): a pause or turn between two images that makes the reader feel a contrast or connection.",
    "Imagery over abstraction: show one concrete moment in nature with the senses instead of explaining a feeling.",
]

_retriever = None


def setup_instrumentation() -> None:
    import oneagent
    oneagent.initialize()


def build_index() -> None:
    """Embed the guide into an in-memory vector store.

    Called once at startup, never at import time and never per request, so the
    batch embedding stays out of the request traces.
    """
    global _retriever
    embeddings = GoogleGenerativeAIEmbeddings(
        model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    )
    store = InMemoryVectorStore.from_texts(GUIDE, embeddings)
    _retriever = store.as_retriever(search_kwargs={"k": 2})


@tool
def search_haiku_guide(query: str) -> str:
    """Search the haiku guide for seasonal words, syllable rules and writing tips."""
    if _retriever is None:
        build_index()
    # retriever.invoke (not similarity_search) is what emits the retrieval span.
    docs = _retriever.invoke(query)
    return "\n".join(doc.page_content for doc in docs)


def _models() -> list[BaseChatModel]:
    # Gemini always runs (GOOGLE_API_KEY). Claude runs only when ANTHROPIC_API_KEY is set.
    models: list[BaseChatModel] = [
        ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
    ]
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        models.append(ChatAnthropic(model=os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")))
    return models


_prompt = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "Write a haiku about {topic}.")]
)


def build_workflow(model: BaseChatModel):
    @chain
    def haiku_workflow(topic: str) -> str:
        """Root workflow: prompt, model asks for the guide, tool runs, model writes the haiku."""
        messages = _prompt.invoke({"topic": topic}).to_messages()

        # Turn 1: the model must call the guide tool. Forcing it keeps the run deterministic.
        ai_msg = model.bind_tools(
            [search_haiku_guide], tool_choice="search_haiku_guide"
        ).invoke(messages)

        tool_msgs = [search_haiku_guide.invoke(call) for call in ai_msg.tool_calls]

        # Turn 2: no tools bound, so the loop always ends after two model calls.
        final = model.invoke(messages + [ai_msg, *tool_msgs])
        return StrOutputParser().invoke(final)

    return haiku_workflow


def write_haiku(topic: str) -> str:
    haikus = [build_workflow(model).invoke(topic) for model in _models()]
    return "\n\n".join(haikus)


def main():
    setup_instrumentation()
    build_index()
    print("=== Haiku Writer (LangChain + OneAgent) ===\n")
    while True:
        topic = input("Topic [q to quit]: ").strip()
        if topic.lower() == "q":
            break
        print("\n" + write_haiku(topic) + "\n")


if __name__ == "__main__":
    main()
