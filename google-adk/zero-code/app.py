import uuid

from dotenv import load_dotenv

load_dotenv()

# No OpenTelemetry setup here on purpose. The app runs under
# "opentelemetry-instrument", which builds the tracer and meter providers from
# OTEL_* environment variables before this module is imported, so ADK's
# module-level instrument creation binds to a real MeterProvider, and the
# semconv opt-ins are already in place, without any in-code bootstrap.

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from agent import academic_coordinator

APP_NAME = "google-adk-zero-code"

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
        app_name=APP_NAME,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id="e2e",
        session_id=str(uuid.uuid4()),
        state={"seminal_paper": req.topic},
    )
    # The coordinator's value is delegation: it reaches academic_websearch_agent and
    # academic_newresearch_agent through AgentTool. Asking only for a summary of a
    # well-known paper lets the model answer from its own weights, producing a trace
    # with no execute_tool span at all, so the derived
    # gen_ai.execute_tool.duration metric is missing on those runs.
    #
    # Ask for recent citing work instead, which the coordinator cannot answer without
    # the websearch tool. That makes the tool call part of the demo's happy path
    # rather than a coin flip.
    message = Content(
        role="user",
        parts=[
            Part(
                text=(
                    f"Summarize the key contributions of the paper: {req.topic}. "
                    "Then use your tools to find recent papers citing it and to suggest "
                    "future research directions based on what you find."
                )
            )
        ],
    )

    async def _run() -> str:
        # Drain the runner rather than returning from inside the loop. Returning early
        # abandons the async generator, which ADK reports as "Root node
        # academic_coordinator was cancelled" and OTel as a "Failed to detach context
        # ... was created in a different Context" ValueError: the generator is closed
        # while spans are still open, so any span that had not ended yet is never
        # exported. Keeping the first final response but consuming the stream to
        # completion lets every span end normally.
        answer = ""
        async for event in runner.run_async(
            user_id="e2e",
            session_id=session.id,
            new_message=message,
        ):
            if not answer and event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        answer = part.text
                        break
        return answer

    result = await _run()
    if not result:
        raise HTTPException(status_code=500, detail="agent returned no response")
    return result
