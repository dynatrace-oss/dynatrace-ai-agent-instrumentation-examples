from main import setup_instrumentation, run_agent

setup_instrumentation()

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MCP Agent Demo")


class InvokeRequest(BaseModel):
    message: str
    # Omit to start a new conversation; pass a previous id to continue it.
    conversation_id: str | None = None


class InvokeResponse(BaseModel):
    response: str
    conversation_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    result, conversation_id = await run_agent(req.message, req.conversation_id)
    return InvokeResponse(response=result, conversation_id=conversation_id)
