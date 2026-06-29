import asyncio
import os

os.environ["TRACELOOP_TELEMETRY"] = "false"
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")

from traceloop.sdk import Traceloop

_dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
_dt_token = os.environ.get("DT_API_TOKEN", "")
Traceloop.init(
    app_name="crewai",
    api_endpoint=f"{_dt_base}/api/v2/otlp",
    headers={"Authorization": f"Api-Token {_dt_token}"},
    disable_batch=True,
    should_enrich_metrics=True,
)

from crewai import Agent, Task, Crew, LLM
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

_model = os.environ.get("MODEL", "genai-demo")
MODEL: str = _model if "/" in _model else f"azure/{_model}"

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    llm = LLM(
        model=MODEL,
        base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-07-01-preview"),
        is_litellm=True,
    )

    def _call() -> str:
        poet = Agent(
            role="Poet",
            goal="Write beautiful haiku poems.",
            backstory="You are a skilled poet specializing in haiku.",
            llm=llm,
        )
        task = Task(
            description="Write a haiku about nature.",
            expected_output="A haiku (3 lines, 5-7-5 syllables).",
            agent=poet,
        )
        crew = Crew(agents=[poet], tasks=[task])
        result = crew.kickoff()
        return str(result)

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
