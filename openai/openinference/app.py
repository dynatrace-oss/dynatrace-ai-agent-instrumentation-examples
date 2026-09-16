import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Iterator

import openai
from fastapi import FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError
from openinference.instrumentation import TraceConfig, using_attributes
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field


SERVICE_NAME = "openai-openinference-genai-semconv"

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


def configure_tracing() -> TracerProvider:
    if not env_is_true("OPENINFERENCE_ENABLE_GENAI_SEMCONV"):
        raise RuntimeError(
            "Set OPENINFERENCE_ENABLE_GENAI_SEMCONV=true so OpenInference "
            "emits OTel gen_ai.* semantic-convention attributes."
        )

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
        }
    )

    provider = TracerProvider(resource=resource)

    # OTLPSpanExporter reads:
    #
    # OTEL_EXPORTER_OTLP_ENDPOINT
    # OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
    # OTEL_EXPORTER_OTLP_HEADERS
    # OTEL_EXPORTER_OTLP_TRACES_HEADERS
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
    )

    trace.set_tracer_provider(provider)

    # TraceConfig reads the OpenInference environment variables, including:
    #
    # OPENINFERENCE_HIDE_INPUTS
    # OPENINFERENCE_HIDE_OUTPUTS
    #
    # Keep both set to true unless message-content capture was explicitly
    # approved.
    OpenAIInstrumentor().instrument(
        tracer_provider=provider,
        config=TraceConfig(),
    )

    logger.info("Tracing configured for service=%s", SERVICE_NAME)

    return provider


def configure_openai_client() -> tuple[openai.OpenAI, str]:
    api_version = os.getenv("OPENAI_API_VERSION")
    api_base = os.getenv("OPENAI_API_BASE")
    api_key = required("OPENAI_API_KEY")

    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "0"))

    if api_version:
        client = openai.AzureOpenAI(
            azure_endpoint=required("OPENAI_API_BASE"),
            api_key=api_key,
            api_version=api_version,
            timeout=timeout,
            max_retries=max_retries,
        )

        provider_name = "azure.openai"
    else:
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base or None,
            timeout=timeout,
            max_retries=max_retries,
        )

        provider_name = "openai"

    logger.info("Configured LLM client provider=%s", provider_name)

    return client, provider_name


tracer_provider = configure_tracing()
openai_client, llm_provider = configure_openai_client()


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
    topic: str = Field(
        default="observability",
        min_length=1,
        max_length=200,
    )

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
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "llm_provider": llm_provider,
    }


@app.post("/haiku", response_model=HaikuResponse)
def create_haiku(request: HaikuRequest) -> HaikuResponse:
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # This matches the existing repository example.
    #
    # Standard OpenAI:
    #   MODEL is the model name.
    #
    # Azure OpenAI:
    #   MODEL is the exact Azure deployment name, not necessarily the
    #   underlying model-family name.
    model = required("MODEL")

    try:
        # OpenInference maps session_id to gen_ai.conversation.id when
        # OPENINFERENCE_ENABLE_GENAI_SEMCONV=true is enabled.
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
                detail="The provider returned a response without text content.",
            )

        return HaikuResponse(
            haiku=content,
            model=response.model,
            conversation_id=conversation_id,
        )

    except APITimeoutError as error:
        logger.warning(
            "%s request timed out: %s",
            llm_provider,
            type(error).__name__,
        )

        raise HTTPException(
            status_code=504,
            detail=(
                f"{llm_provider} request timed out. Check outbound HTTPS "
                "access to the configured endpoint and the approved proxy."
            ),
        ) from error

    except APIConnectionError as error:
        logger.warning(
            "%s connection failed: %s",
            llm_provider,
            type(error).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not connect to {llm_provider}. Check the configured "
                "endpoint, DNS, TLS inspection, outbound HTTPS access, and "
                "proxy configuration."
            ),
        ) from error

    except APIStatusError as error:
        # The URL and response body help diagnose Azure deployment, endpoint,
        # and API-version mismatches. Authentication headers are not logged.
        logger.warning(
            "%s returned status=%s request_url=%s response=%s",
            llm_provider,
            error.status_code,
            error.request.url,
            error.response.text,
        )

        raise HTTPException(
            status_code=502,
            detail=f"{llm_provider} returned HTTP status {error.status_code}.",
        ) from error

    except HTTPException:
        raise

    except Exception as error:
        logger.exception(
            "Unexpected %s request failure",
            llm_provider,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected provider request failure: "
                f"{type(error).__name__}"
            ),
        ) from error

    finally:
        # Reduce the wait for spans during local validation.
        tracer_provider.force_flush(timeout_millis=10_000)