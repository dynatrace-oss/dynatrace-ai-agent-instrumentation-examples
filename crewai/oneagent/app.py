import asyncio
import os

from crewai import LLM, Agent, Crew, Task
from crewai.flow import ConversationConfig, Flow
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

DEPLOYMENT: str = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or "genai-demo"

app = FastAPI(title="crewai-oneagent")


class HaikuRequest(BaseModel):
    topic: str = "nature"


class ChatRequest(BaseModel):
    message: str
    session_id: str = "demo"


def _llm() -> LLM:
    # custom_openai=True forces CrewAI's native OpenAI provider (openai.OpenAI).
    # Without it, a deployment name CrewAI does not know falls back to LiteLLM.
    # Azure's /openai/v1/ endpoint accepts the plain OpenAI client. Streaming is
    # off because OneAgent's OpenAI sensor does not reassemble streamed chunks.
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    return LLM(
        model=DEPLOYMENT,
        custom_openai=True,
        base_url=f"{endpoint}/openai/v1/",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        stream=False,
    )


def _run_crew(description: str) -> str:
    poet = Agent(
        role="Poet",
        goal="Write beautiful haiku poems.",
        backstory="You are a skilled poet specializing in haiku.",
        llm=_llm(),
    )
    task = Task(
        description=description,
        expected_output="A haiku (3 lines, 5-7-5 syllables).",
        agent=poet,
    )
    return str(Crew(agents=[poet], tasks=[task]).kickoff())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku(req: HaikuRequest | None = None) -> str:
    topic = req.topic if req else "nature"
    return await asyncio.to_thread(_run_crew, f"Write a haiku about {topic}.")


# One conversational Flow per session, kept in memory so later turns see the
# history of earlier ones.
_flows: dict[str, Flow] = {}


def _chat_flow() -> Flow:
    @ConversationConfig(
        llm=_llm(),
        system_prompt="You are a skilled poet. Answer in haiku (3 lines, 5-7-5).",
    )
    class ChatFlow(Flow):
        pass

    return ChatFlow()


def _chat_turn(message: str, session_id: str) -> str:
    flow = _flows.get(session_id)
    if flow is None:
        flow = _flows[session_id] = _chat_flow()
    return str(flow.handle_turn(message, session_id=session_id))


@app.post("/chat", response_class=PlainTextResponse)
async def chat(req: ChatRequest) -> str:
    return await asyncio.to_thread(_chat_turn, req.message, req.session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
