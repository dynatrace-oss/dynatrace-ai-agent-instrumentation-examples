import asyncio
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import run_agent

app = FastAPI(title="aws-bedrock-agents-oneagent")


class AgentRequest(BaseModel):
    task: str


class AgentResponse(BaseModel):
    task: str
    result: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(req: AgentRequest):
    if not req.task.strip():
        raise HTTPException(status_code=400, detail="task must not be empty")
    result = await asyncio.to_thread(run_agent, req.task)
    return AgentResponse(task=req.task, result=result)
