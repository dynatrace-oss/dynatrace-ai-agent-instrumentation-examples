import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from traceloop.sdk import Traceloop

Traceloop.init(
    app_name="google-adk-samples",
    api_endpoint=os.environ["OTEL_ENDPOINT"],
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    disable_batch=True,
)

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from agent import academic_coordinator

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
        agent=academic_coordinator,
        app_name="google-adk-samples",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="google-adk-samples",
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

    return await _run()
