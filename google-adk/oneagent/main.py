import os

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

APP_NAME = "haiku_app"
USER_ID = "demo"


def setup_instrumentation() -> None:
    import oneagent

    oneagent.initialize()


def _build_runner() -> InMemoryRunner:
    # Gemini API key comes from GOOGLE_API_KEY (see .env.sample).
    agent = LlmAgent(
        name="haiku_agent",
        model=os.environ.get("MODEL", "gemini-3.1-flash-lite"),
        instruction="You write a single haiku (5-7-5 syllables) about the topic the user gives. Reply with the haiku only.",
    )
    return InMemoryRunner(agent=agent, app_name=APP_NAME)


_runner = _build_runner()


async def write_haiku(topic: str) -> str:
    session = await _runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=f"Write a haiku about {topic}.")])
    text = ""
    async for event in _runner.run_async(user_id=USER_ID, session_id=session.id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
    return text
