import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import run_orchestrator, setup_instrumentation

setup_instrumentation()

app = FastAPI(title="aws-bedrock-agentcore-opentelemetry")


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
