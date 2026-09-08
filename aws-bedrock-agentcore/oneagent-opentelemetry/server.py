import asyncio
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import run_orchestrator, setup_metrics_instrumentation

# Metrics only -- see main.py's module docstring for why. This app never
# configures its own OTel SDK TracerProvider/span exporter; it relies
# entirely on OneAgent's "OpenTelemetry (Python)" opt-in to capture and
# correlate the span main.py creates via the plain OTel API.
setup_metrics_instrumentation()

# FastAPI(title=...) also sets the service.name OneAgent derives its
# Smartscape SERVICE entity from, which is what a query scoped to one
# service.name uses to find both OneAgent's own HTTP entry span and this
# app's manually created OTel span in the same trace.
_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "aws-bedrock-agentcore-example")
app = FastAPI(title=_SERVICE_NAME)


class InvokeRequest(BaseModel):
    topic: str


class InvokeResponse(BaseModel):
    topic: str
    result: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    trace_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    # async def + asyncio.to_thread (not a sync `def` route) so the OTel
    # context created here is explicitly propagated into the worker thread
    # that calls boto3 -- a plain sync route dispatched to FastAPI's default
    # thread pool loses span parentage with botocore calls (see the
    # fastapi-sync-botocore-span-propagation write-up in the
    # ai-observability-workspace repo).
    result = await asyncio.to_thread(run_orchestrator, req.topic)
    usage = result.get("usage") or {}
    return InvokeResponse(
        topic=req.topic,
        result=result["text"],
        input_tokens=usage.get("inputTokens"),
        output_tokens=usage.get("outputTokens"),
        trace_id=result["trace_id"],
    )
