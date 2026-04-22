from __future__ import annotations

import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# OTel must be set up before any pydantic-ai imports so the global
# tracer/meter providers are in place when InstrumentationSettings picks them up.
from otel_setup import setup_otel

_tracer_provider, _meter_provider = setup_otel("pydantic-ai-music-agent")

from opentelemetry import trace
from fastapi import FastAPI, HTTPException
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

# Active Bedrock cross-region inference profile IDs (us. prefix required)
BEDROCK_MODEL_SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_MODEL_HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# pydantic-ai native OTel instrumentation — emits GenAI semantic convention spans
# automatically for every agent.run() call (model, tokens, latency, content).
_instrumentation = InstrumentationSettings(
    tracer_provider=_tracer_provider,
    meter_provider=_meter_provider,
    include_content=True,  # capture prompts & completions as span events
)

tracer = trace.get_tracer("music-agent-api")


def _bedrock_provider() -> BedrockProvider:
    return BedrockProvider(
        aws_access_key_id=os.environ["Bedrock_username"],
        aws_secret_access_key=os.environ["bedrock_key"],
        region_name="us-east-1",
    )


def build_azure_model() -> tuple[OpenAIModel, str, str]:
    # Azure endpoint is only reachable from the corporate network;
    # falls back to a Bedrock model when unavailable.
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


app = FastAPI(title="Music History Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str
    provider: str
    model: str


@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    builders = [build_azure_model, build_bedrock_sonnet, build_bedrock_haiku]
    random.shuffle(builders)

    last_error: Exception | None = None
    for builder in builders:
        try:
            model, provider, model_name = builder()

            # Outer span gives API-level context; pydantic-ai adds nested GenAI spans.
            with tracer.start_as_current_span(
                "music_agent.ask",
                kind=trace.SpanKind.SERVER,
            ) as span:
                span.set_attribute("gen_ai.provider.name", provider)
                span.set_attribute("gen_ai.request.model", model_name)
                span.set_attribute("music_agent.question", request.question)

                agent = Agent(
                    model=model,
                    system_prompt=MUSIC_SYSTEM_PROMPT,
                    instrument=_instrumentation,
                )
                result = await agent.run(request.question)
                answer = result.output if hasattr(result, "output") else result.data

                # Record token usage on the outer span
                usage = result.usage()
                if usage:
                    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens or 0)
                    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens or 0)

            return AnswerResponse(answer=str(answer), provider=provider, model=model_name)

        except Exception as exc:
            last_error = exc
            continue

    raise HTTPException(status_code=500, detail=f"All providers failed: {last_error}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
