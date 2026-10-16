import logging
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

# OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (make run points it at the
# local collector, which derives gen_ai.* metrics from the spans).
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from openinference.instrumentation import using_session
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

_service_name = os.environ.get("OTEL_SERVICE_NAME", "google-adk/openinference")
provider = TracerProvider(resource=Resource.create({SERVICE_NAME: _service_name}))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
GoogleADKInstrumentor().instrument(tracer_provider=provider)

from fastapi import FastAPI, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from agent import academic_coordinator

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
APP_NAME = "google-adk-openinference"
USER_ID = "e2e"

session_service = InMemorySessionService()

app = FastAPI()


class ResearchRequest(BaseModel):
    topic: str = "Attention is All You Need"
    # Reuse to continue a conversation; a new id is generated when absent.
    conversation_id: str | None = None


class ResearchResponse(BaseModel):
    conversation_id: str
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


async def _get_or_create_session(conversation_id: str, topic: str):
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=conversation_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=conversation_id,
            state={"seminal_paper": topic},
        )
    return session


@app.post("/research", response_model=ResearchResponse)
async def research(req: ResearchRequest) -> ResearchResponse:
    conversation_id = req.conversation_id or str(uuid.uuid4())
    runner = Runner(
        agent=academic_coordinator,
        app_name=APP_NAME,
        session_service=session_service,
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
    #
    # The summary is requested as a short paraphrase: asking for a plain summary of a
    # famous paper tends to elicit near-verbatim abstract text, which Gemini aborts
    # with finish_reason RECITATION and no content.
    message = Content(
        role="user",
        parts=[
            Part(
                text=(
                    f"In your own words, in at most three sentences, describe the key "
                    f"contributions of the paper: {req.topic}. "
                    "Then use your tools to find recent papers citing it and to suggest "
                    "future research directions based on what you find."
                )
            )
        ],
    )

    async def _run() -> tuple[str, list[str]]:
        # The ADK session id is the conversation id, so multi-turn history and
        # gen_ai.conversation.id (from OpenInference session.id) stay aligned.
        session = await _get_or_create_session(conversation_id, req.topic)
        # Drain the runner rather than returning from inside the loop. Returning early
        # abandons the async generator, which ADK reports as "Root node
        # academic_coordinator was cancelled" and OTel as a "Failed to detach context
        # ... was created in a different Context" ValueError: the generator is closed
        # while spans are still open, so any span that had not ended yet is never
        # exported. Keeping the first final response but consuming the stream to
        # completion lets every span end normally.
        answer = ""
        errors: list[str] = []
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session.id,
            new_message=message,
        ):
            # A failed model call (quota, safety block, ...) arrives as an event with an
            # error code and no content; record it so an empty answer can be explained.
            if event.error_code or event.error_message:
                detail = f"{event.author}: {event.error_code}: {event.error_message}"
                logger.error("ADK model error event: %s", detail)
                errors.append(detail)
            if not answer and event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        answer = part.text
                        break
        return answer, errors

    # Model-side aborts such as RECITATION are non-deterministic; retry the turn.
    # using_session puts the conversation id on every span of the turn.
    with using_session(conversation_id):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            result, errors = await _run()
            if result or not errors:
                break
            logger.warning("attempt %d/%d failed with model errors", attempt, MAX_ATTEMPTS)
    if not result:
        if errors:
            raise HTTPException(status_code=502, detail=f"agent model error: {'; '.join(errors)}")
        raise HTTPException(status_code=500, detail="agent returned no response")
    return ResearchResponse(conversation_id=conversation_id, answer=result)
