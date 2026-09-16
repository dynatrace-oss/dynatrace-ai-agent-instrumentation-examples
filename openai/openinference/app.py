import os
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from openinference.instrumentation import TraceConfig, using_attributes
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field


SERVICE_NAME = "openai-openinference-genai-semconv"

logger = logging.getLogger("uvicorn.error")

def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def configure_tracing() -> TracerProvider:
    if os.getenv("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "").lower() != "true":
        raise RuntimeError(
            "Set OPENINFERENCE_ENABLE_GENAI_SEMCONV=true so OpenInference emits "
            "OTel GenAI semantic-convention attributes required by AI Observability."
        )

    exporter = OTLPSpanExporter(
        endpoint=(
                required("DT_ENDPOINT").rstrip("/")
                + "/api/v2/otlp/v1/traces"
        ),
        headers={
            "Authorization": f"Api-Token {required('DT_API_TOKEN')}",
        },
    )

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": SERVICE_NAME,
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # TraceConfig reads OPENINFERENCE_ENABLE_GENAI_SEMCONV and
    # the OPENINFERENCE_HIDE_* privacy settings from the environment.
    OpenAIInstrumentor().instrument(
        tracer_provider=provider,
        config=TraceConfig(),
    )

    return provider


tracer_provider = configure_tracing()
openai_client = OpenAI(api_key=required("OPENAI_API_KEY"))


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterator[None]:
    yield
    tracer_provider.force_flush()
    tracer_provider.shutdown()


app = FastAPI(
    title="OpenAI OpenInference GenAI semantic-convention example",
    lifespan=lifespan,
)


class HaikuRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)


class HaikuResponse(BaseModel):
    topic: str
    haiku: str
    conversation_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/haiku", response_model=HaikuResponse)
def create_haiku(request: HaikuRequest) -> HaikuResponse:
    conversation_id = str(uuid.uuid4())

    try:
        with using_attributes(session_id=conversation_id):
            response = openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write concise haiku. Return only the haiku, "
                            "using three lines."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Write a haiku about {request.topic}.",
                    },
                ],
                max_completion_tokens=100,
            )
    except Exception as error:
        logger.exception(
            "OpenAI request failed: type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI request failed: {type(error).__name__}",
        ) from error

    haiku = response.choices[0].message.content
    if not haiku:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned an empty response.",
        )

    return HaikuResponse(
        topic=request.topic,
        haiku=haiku.strip(),
        conversation_id=conversation_id,
    )