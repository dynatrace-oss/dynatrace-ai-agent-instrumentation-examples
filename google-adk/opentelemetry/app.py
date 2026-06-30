import asyncio
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from traceloop.sdk import Traceloop

Traceloop.init(
    app_name="google-adk-samples",
    api_endpoint=os.environ["DT_OTEL_ENDPOINT"],
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    disable_batch=True,
)

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

MODEL = os.environ.get("MODEL", "gemini-2.0-flash")

haiku_agent = LlmAgent(
    name="haiku_agent",
    model=MODEL,
    instruction=(
        "You are a haiku poet. Write a haiku about the given topic. "
        "Return only the haiku, nothing else."
    ),
)

session_service = InMemorySessionService()

app = FastAPI()


class HaikuRequest(BaseModel):
    topic: str = "observability"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku(req: HaikuRequest) -> str:
    runner = Runner(
        agent=haiku_agent,
        app_name="google-adk-samples",
        session_service=session_service,
    )
    session = session_service.create_session(
        app_name="google-adk-samples",
        user_id="e2e",
        session_id=str(uuid.uuid4()),
    )
    message = Content(role="user", parts=[Part(text=f"Write a haiku about {req.topic}.")])

    async def _run() -> str:
        async for event in runner.run_async(
            user_id="e2e",
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        return part.text
        return ""

    return await _run()
