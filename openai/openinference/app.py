import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from openinference.instrumentation import TraceConfig, using_attributes
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field

SERVICE_NAME = "openai-openinference-genai-semconv"
DEFAULT_MODEL = "gpt-4o-mini"

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(SERVICE_NAME)


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_is_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def dynatrace_trace_endpoint() -> str:
    endpoint = required("DT_ENDPOINT").rstrip("/")

    if endpoint.endswith("/v1/traces"):
        return endpoint
    if endpoint.endswith("/api/v2/otlp"):
        return endpoint + "/v1/traces"
    return endpoint + "/api/v2/otlp/v1/traces"


def configure_tracing() -> TracerProvider:
    if not env_is_true("OPENINFERENCE_ENABLE_GENAI_SEMCONV"):
        raise RuntimeError(
            "Set OPENINFERENCE_ENABLE_GENAI_SEMCONV=true so OpenInference emits "
            "OTel gen_ai.* semantic-convention attributes."
        )

    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=dynatrace_trace_endpoint(),
        headers={"Authorization": f"Api-Token {required('DT_API_TOKEN')}"},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Prompt and completion capture is disabled unless explicitly approved.
    capture_content = env_is_true("CAPTURE_MESSAGE_CONTENT", default=False)
    trace_config = TraceConfig(
        hide_inputs=not capture_content,
        hide_outputs=not capture_content,
    )

    OpenAIInstrumentor().instrument(
        tracer_provider=provider,
        config=trace_config,
    )

    logger.info(
        "Tracing configured for service=%s; message_content_capture=%s",
        SERVICE_NAME,
        capture_content,
    )
    return provider


tracer_provider = configure_tracing()
openai_client = OpenAI(
    api_key=required("OPENAI_API_KEY"),
    timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
    max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "0")),
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterator[None]:
    try:
        yield
    finally:
        tracer_provider.force_flush(timeout_millis=10_000)
        tracer_provider.shutdown()


app = FastAPI(
    title="OpenAI OpenInference GenAI semantic conventions",
    version="1.0.0",
    lifespan=lifespan,
)


class HaikuRequest(BaseModel):
    topic: str = Field(default="observability", min_length=1, max_length=200)
    conversation_id: str | None = Field(
        default=None,
        description="Reuse this value for all requests in the same conversation.",
    )


class HaikuResponse(BaseModel):
    haiku: str
    model: str
    conversation_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/haiku", response_model=HaikuResponse)
def create_haiku(request: HaikuRequest) -> HaikuResponse:
    conversation_id = request.conversation_id or str(uuid.uuid4())
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    try:
        # OpenInference maps session_id to gen_ai.conversation.id when the
        # GenAI semantic-convention compatibility flag is enabled.
        with using_attributes(session_id=conversation_id):
            response = openai_client.chat.completions.create(
                model=model,
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

        content = response.choices[0].message.content
        if not content:
            raise HTTPException(
                status_code=502,
                detail="OpenAI returned a response without text content.",
            )

        return HaikuResponse(
            haiku=content,
            model=response.model,
            conversation_id=conversation_id,
        )

    except APITimeoutError as error:
        logger.warning("OpenAI request timed out: %s", type(error).__name__)
        raise HTTPException(
            status_code=504,
            detail=(
                "OpenAI request timed out. Check outbound HTTPS access to "
                "api.openai.com:443 and the approved HTTPS proxy configuration."
            ),
        ) from error

    except APIConnectionError as error:
        logger.warning("OpenAI connection failed: %s", type(error).__name__)
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not connect to OpenAI. Check DNS, TLS inspection, outbound "
                "HTTPS access, and the approved HTTPS proxy configuration."
            ),
        ) from error

    except APIStatusError as error:
        logger.warning(
            "OpenAI returned an HTTP error: status_code=%s",
            error.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI returned HTTP status {error.status_code}.",
        ) from error

    except HTTPException:
        raise

    except Exception as error:
        logger.exception("Unexpected OpenAI request failure")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected OpenAI request failure: {type(error).__name__}",
        ) from error

    finally:
        # Make local validation less dependent on the batch export interval.
        tracer_provider.force_flush(timeout_millis=10_000)
