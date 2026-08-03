"""Deterministic GenAI span fixtures for dt-evals end-to-end tests.

Unlike the other examples in this repo, this one never calls a real LLM. It
drives a real, Traceloop-instrumented LangChain chat model — but the model is a
`FixtureModel` (a `FakeListChatModel` with fixed model name + token usage)
pre-programmed with the canned answers in `fixtures.json`. Because the input
prompts and the answers are both fixed, every run emits identical GenAI spans (a
toxic answer stays toxic, a clean one stays clean), so an eval suite can assert
against them as a regression baseline.

Multi-turn conversations are emitted as one span per turn, linked by a shared
`gen_ai.conversation.id` — the same shape a production chatbot produces. See
../SPEC.md for the full design.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fixtures import load_fixtures
from ingest import ingest_cases
from tracing import init_tracing

FIXTURES_PATH = os.environ.get("FIXTURES_PATH", "fixtures.json")
SERVICE_NAME, CASES = load_fixtures(FIXTURES_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Export straight to the Dynatrace tenant — no collector needed.
    base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
    token = os.environ.get("DT_API_TOKEN", "")
    init_tracing(
        SERVICE_NAME,
        api_endpoint=f"{base}/api/v2/otlp",
        headers={"Authorization": f"Api-Token {token}"},
    )
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest():
    """Ship every fixture as GenAI spans. Returns the case names emitted."""
    names = ingest_cases(CASES)
    return {"ingested": len(names), "cases": names}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
