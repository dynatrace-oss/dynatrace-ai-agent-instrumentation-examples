import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import setup_instrumentation, write_haiku

setup_instrumentation()

app = FastAPI(title="langgraph-oneagent")


class HaikuRequest(BaseModel):
    topic: str


class HaikuResponse(BaseModel):
    topic: str
    haiku: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_model=HaikuResponse)
async def haiku(req: HaikuRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    result = await asyncio.to_thread(write_haiku, req.topic)
    return HaikuResponse(topic=req.topic, haiku=result)
