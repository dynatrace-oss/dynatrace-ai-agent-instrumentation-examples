import os

from google.adk.agents import LlmAgent

MODEL = os.environ.get("MODEL", "gemini-3.1-flash-lite")

research_agent = LlmAgent(
    name="research_assistant",
    model=MODEL,
    description="Summarizes academic papers and research topics.",
    instruction=(
        "You are an AI Research Assistant. When given a paper title or research topic, "
        "provide a concise summary of its key contributions, methodology, and impact. "
        "Keep your response to 3-5 sentences."
    ),
)
