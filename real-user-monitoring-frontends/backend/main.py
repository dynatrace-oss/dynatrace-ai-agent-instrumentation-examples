from __future__ import annotations

import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# OTel must be initialised before pydantic-ai imports
from otel_setup import setup_otel

_tracer_provider, _meter_provider = setup_otel("rum-music-agent")

from opentelemetry import trace
from opentelemetry.propagate import extract  # extracts W3C traceparent from RUM headers
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pydantic_ai import Agent, InstrumentationSettings
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider
from pydantic_ai.providers.bedrock import BedrockProvider

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

MUSIC_SYSTEM_PROMPT = (
    "You are an expert music historian specializing in jazz, classic rock, and classical music. "
    "Provide engaging, accurate, richly detailed answers that include interesting anecdotes, "
    "historical context, and connections between musicians and movements. "
    "Keep responses informative but conversational — typically 2–4 paragraphs."
)

BEDROCK_MODEL_SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_MODEL_HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_instrumentation = InstrumentationSettings(
    tracer_provider=_tracer_provider,
    meter_provider=_meter_provider,
    include_content=True,
)

tracer = trace.get_tracer("rum-music-agent-api")


def _bedrock_provider() -> BedrockProvider:
    return BedrockProvider(
        aws_access_key_id=os.environ["Bedrock_username"],
        aws_secret_access_key=os.environ["bedrock_key"],
        region_name="us-east-1",
    )


def build_azure_model() -> tuple[OpenAIModel, str, str]:
    provider = AzureProvider(
        azure_endpoint=os.environ["Azure_openai_endpoint"],
        api_key=os.environ["Azure_openai_key"],
        api_version="2024-02-01",
    )
    deployment = os.environ["Azure_openai_deployment"]
    return OpenAIModel(deployment, provider=provider), "Azure OpenAI", deployment


def build_bedrock_sonnet() -> tuple[BedrockConverseModel, str, str]:
    return (
        BedrockConverseModel(BEDROCK_MODEL_SONNET, provider=_bedrock_provider()),
        "AWS Bedrock",
        BEDROCK_MODEL_SONNET,
    )


def build_bedrock_haiku() -> tuple[BedrockConverseModel, str, str]:
    return (
        BedrockConverseModel(BEDROCK_MODEL_HAIKU, provider=_bedrock_provider()),
        "AWS Bedrock",
        BEDROCK_MODEL_HAIKU,
    )


app = FastAPI(title="RUM Music Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-ID"],
)


class QuestionRequest(BaseModel):
    question: str
    conversation_id: str  # generated client-side, propagated through every exchange


class AnswerResponse(BaseModel):
    answer: str
    provider: str
    model: str
    conversation_id: str


class FeedbackRequest(BaseModel):
    rating: str          # "thumbs_up" | "thumbs_down"
    question: str
    conversation_id: str
    provider: str
    model: str


@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/feedback", status_code=204)
async def record_feedback(http_request: Request, body: FeedbackRequest):
    incoming_ctx = extract(dict(http_request.headers))
    with tracer.start_as_current_span(
        "music_agent.feedback",
        context=incoming_ctx,
        kind=trace.SpanKind.SERVER,
    ) as span:
        span.set_attribute("conversation.id", body.conversation_id)
        span.set_attribute("feedback.rating", body.rating)
        span.set_attribute("feedback.question", body.question)
        span.set_attribute("gen_ai.provider.name", body.provider)
        span.set_attribute("gen_ai.request.model", body.model)


@app.post("/api/ask", response_model=AnswerResponse)
async def ask_question(http_request: Request, body: QuestionRequest):
    # Extract W3C trace context injected by Dynatrace RUM JS (traceparent / tracestate).
    # This links the backend span as a child of the browser user-action span.
    incoming_ctx = extract(dict(http_request.headers))

    builders = [build_azure_model, build_bedrock_sonnet, build_bedrock_haiku]
    random.shuffle(builders)

    last_error: Exception | None = None
    for builder in builders:
        try:
            model, provider, model_name = builder()

            with tracer.start_as_current_span(
                "music_agent.ask",
                context=incoming_ctx,          # parent = RUM browser span
                kind=trace.SpanKind.SERVER,
            ) as span:
                # conversation.id ties every exchange in a session together.
                # Filter in DQL: fetch spans | filter conversation.id == "<id>"
                span.set_attribute("conversation.id", body.conversation_id)
                span.set_attribute("gen_ai.provider.name", provider)
                span.set_attribute("gen_ai.request.model", model_name)
                span.set_attribute("music_agent.question", body.question)

                agent = Agent(
                    model=model,
                    system_prompt=MUSIC_SYSTEM_PROMPT,
                    instrument=_instrumentation,
                )
                result = await agent.run(body.question)
                answer = result.output if hasattr(result, "output") else result.data

                usage = result.usage()
                if usage:
                    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens or 0)
                    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens or 0)

            return AnswerResponse(
                answer=str(answer),
                provider=provider,
                model=model_name,
                conversation_id=body.conversation_id,
            )

        except Exception as exc:
            last_error = exc
            continue

    raise HTTPException(status_code=500, detail=f"All providers failed: {last_error}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
