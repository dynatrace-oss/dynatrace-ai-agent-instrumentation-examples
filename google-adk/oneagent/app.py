import os
import uuid

from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from agent import research_agent

APP_NAME = "google-adk-research"

session_service = InMemorySessionService()

app = FastAPI()


class ResearchRequest(BaseModel):
    topic: str = "Attention is All You Need"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/research", response_class=PlainTextResponse)
async def research(req: ResearchRequest) -> str:
    runner = Runner(
        agent=research_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id="e2e",
        session_id=str(uuid.uuid4()),
    )
    message = Content(
        role="user",
        parts=[Part(text=f"Briefly summarize the key contributions of the paper: {req.topic}")],
    )

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

    result = await _run()
    if not result:
        raise HTTPException(status_code=500, detail="agent returned no response")
    return result
