import asyncio
import contextvars
import json
import os
from uuid import uuid4

from openinference.instrumentation import using_attributes
from openinference.instrumentation.crewai import CrewAIInstrumentor
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Disable CrewAI's own anonymous telemetry so only OpenInference spans are exported.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

# Emit OTel GenAI semantic-convention attributes (gen_ai.*) natively from
# OpenInference instrumentors.
os.environ.setdefault("OPENINFERENCE_ENABLE_GENAI_SEMCONV", "true")

_service_name = os.environ.get("OTEL_SERVICE_NAME", "crewai/openinference")
_resource = Resource.create({SERVICE_NAME: _service_name})
_tracer_provider = trace_sdk.TracerProvider(resource=_resource)

# OpenInference keeps the system prompt inside gen_ai.input.messages and does
# not set gen_ai.system_instructions, so set it on the LiteLLM spans from the
# agent persona of the current request.
_system_instructions: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "system_instructions", default=None
)


class SystemInstructionsSpanProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        instructions = _system_instructions.get()
        if instructions and span.name in ("completion", "acompletion"):
            span.set_attribute(
                "gen_ai.system_instructions",
                json.dumps([{"type": "text", "content": instructions}]),
            )


_tracer_provider.add_span_processor(SystemInstructionsSpanProcessor())
_tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_tracer_provider)

# CrewAIInstrumentor traces crews, agents and tasks; CrewAI reaches the model
# through LiteLLM, so LiteLLMInstrumentor adds the LLM spans.
CrewAIInstrumentor().instrument(tracer_provider=_tracer_provider)
LiteLLMInstrumentor().instrument(tracer_provider=_tracer_provider)

from crewai import LLM, Agent, Crew, Task
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

_model = os.environ.get("MODEL", "genai-demo")
MODEL: str = _model if "/" in _model else f"azure/{_model}"

app = FastAPI()


class HaikuRequest(BaseModel):
    topic: str = "nature"
    conversation_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku(response: Response, req: HaikuRequest | None = None) -> str:
    topic = req.topic if req else "nature"
    # Reuse the client's conversation id across turns; start a new one if absent.
    conversation_id = (req.conversation_id if req else None) or str(uuid4())
    response.headers["X-Conversation-Id"] = conversation_id

    def _call() -> str:
        llm = LLM(
            model=MODEL,
            base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("OPENAI_API_VERSION", "2024-07-01-preview"),
            temperature=0.7,
            is_litellm=True,
        )
        poet = Agent(
            role="Poet",
            goal="Write beautiful haiku poems.",
            backstory="You are a skilled poet specializing in haiku.",
            llm=llm,
        )
        task = Task(
            description=f"Write a haiku about {topic}.",
            expected_output="A haiku (3 lines, 5-7-5 syllables).",
            agent=poet,
        )
        # Same text CrewAI renders as the system message for this agent.
        _system_instructions.set(
            f"You are {poet.role}. {poet.backstory}\nYour personal goal is: {poet.goal}"
        )
        # session.id is emitted as gen_ai.conversation.id on every span of the turn.
        with using_attributes(session_id=conversation_id):
            result = Crew(agents=[poet], tasks=[task]).kickoff()
        return str(result)

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
