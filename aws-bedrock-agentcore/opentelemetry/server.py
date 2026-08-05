import asyncio
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import run_orchestrator, setup_instrumentation  # noqa: F401 -- kept unused, see below

# DIAGNOSTIC BRANCH (experiment/agentcore-oneagent-baseline): deliberately NOT
# calling setup_instrumentation(). This app never establishes its own OTel SDK
# TracerProvider/MeterProvider (main.py's get_tracer()/get_meter() calls fall
# back to no-op proxies), isolating whether OneAgent's own FastAPI/Starlette
# auto-instrumentation fires normally when the process doesn't also run its
# own OTel SDK -- which is what the real PoC (aws-bedrock-agentcore/opentelemetry,
# main branch of this PR) does and where OneAgent produced zero spans.

# Must match the service.name set on the OTel Resource in main.py
# (OTEL_SERVICE_NAME, same default). When OneAgent is also installed on the
# host, it derives a Smartscape SERVICE entity's service.name from this
# FastAPI title -- keeping the two in sync is what lets a query scoped to one
# service.name find both OneAgent's own spans and this app's manually created
# OTel spans in the same trace.
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
