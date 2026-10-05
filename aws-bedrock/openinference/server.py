import asyncio
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import apply_guardrail, setup_instrumentation, write_haiku

setup_instrumentation()

app = FastAPI(title="Haiku Writer")


class HaikuRequest(BaseModel):
    topic: str


class HaikuResponse(BaseModel):
    topic: str
    haiku: str


class GuardrailRequest(BaseModel):
    text: str


class GuardrailResponse(BaseModel):
    text: str
    action: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_model=HaikuResponse)
async def haiku(req: HaikuRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic must not be empty")
    result = await asyncio.to_thread(write_haiku, req.topic)
    return HaikuResponse(topic=req.topic, haiku=result)


@app.post("/guardrail", response_model=GuardrailResponse)
async def guardrail(req: GuardrailRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    result = await asyncio.to_thread(apply_guardrail, req.text)
    return GuardrailResponse(text=req.text, action=result)
