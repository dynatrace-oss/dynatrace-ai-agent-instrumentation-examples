"""Deterministic GenAI span fixtures for dt-evals end-to-end tests.

Unlike the other examples in this repo, this one never calls a real LLM. It
drives a real, Traceloop-instrumented LangChain chat model — but the model is a
`FakeListChatModel` pre-programmed with a sequence of canned answers from
fixtures.json. Because the input prompts and the answers are both fixed, every
run emits identical GenAI spans (a toxic answer stays toxic, a clean one stays
clean), so an eval suite can assert against them as a regression baseline.

The spans are produced by the same instrumentation path a real LangChain app
uses, so they carry exactly the attribute shape dt-evals sees in production —
no hand-built spans.
"""

import json
import os
from pathlib import Path

os.environ["TRACELOOP_TELEMETRY"] = "false"
# Dynatrace ingests delta metrics only; export delta temporality from the SDK.
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
# Capture message content as gen_ai.input.messages / gen_ai.output.messages
# (off by default in the GenAI semconv).
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

FIXTURES = json.loads((Path(__file__).parent / "fixtures.json").read_text())
os.environ.setdefault("OTEL_SERVICE_NAME", FIXTURES.get("service_name", "dt-evals-fixtures"))

from traceloop.sdk import Traceloop

# Export straight to the Dynatrace tenant — no collector needed.
_dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
_dt_token = os.environ.get("DT_API_TOKEN", "")
Traceloop.init(
    app_name=os.environ["OTEL_SERVICE_NAME"],
    api_endpoint=f"{_dt_base}/api/v2/otlp",
    headers={"Authorization": f"Api-Token {_dt_token}"},
    disable_batch=True,
    should_enrich_metrics=True,
)

from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage

app = FastAPI()


def _ingest_all() -> list[str]:
    """Replay every fixture through a pre-programmed fake chat model.

    The fake model returns the canned answers in fixture order, so each
    invocation emits one GenAI chat span with a fixed prompt and fixed answer.
    """
    cases = FIXTURES["cases"]
    model = FakeListChatModel(responses=[c["response"] for c in cases])
    for case in cases:
        model.invoke(
            [
                SystemMessage(content=case["system"]),
                HumanMessage(content=case["user"]),
            ]
        )
    return [c["name"] for c in cases]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest():
    """Ship every fixture as a GenAI span. Returns the case names emitted."""
    names = _ingest_all()
    return {"ingested": len(names), "cases": names}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
