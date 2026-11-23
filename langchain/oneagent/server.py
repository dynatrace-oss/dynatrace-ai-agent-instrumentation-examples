import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import build_index, setup_instrumentation, write_haiku

setup_instrumentation()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Index the haiku guide once, outside any request.
    await asyncio.to_thread(build_index)
    yield


app = FastAPI(title="langchain-oneagent", lifespan=lifespan)


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
