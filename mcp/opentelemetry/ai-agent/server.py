from main import setup_instrumentation, run_agent

setup_instrumentation()

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MCP Agent Demo")


class InvokeRequest(BaseModel):
    message: str


class InvokeResponse(BaseModel):
    response: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    result = await run_agent(req.message)
    return InvokeResponse(response=result)
