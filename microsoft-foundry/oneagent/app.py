import asyncio
import os
import time
from typing import Any, Optional

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.core.credentials import AccessToken
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

ENDPOINT: str = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")
MODEL: str = os.environ.get("MODEL", "gpt-4o-mini")
AGENT_NAME: str = os.environ.get("AGENT_NAME", "haiku-agent")

app = FastAPI(title="microsoft-foundry-oneagent")


class _StaticTokenCredential:
    """Bearer token from FOUNDRY_STATIC_TOKEN; used against the e2e mock only."""

    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self, *_scopes: str, **_kwargs: Any) -> AccessToken:
        return AccessToken(self._token, int(time.time()) + 3600)


def _credential():
    token = os.environ.get("FOUNDRY_STATIC_TOKEN")
    return _StaticTokenCredential(token) if token else DefaultAzureCredential()


class HaikuRequest(BaseModel):
    topic: str = "observability"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku(req: Optional[HaikuRequest] = None) -> str:
    topic = (req or HaikuRequest()).topic

    def _call() -> str:
        client = AIProjectClient(endpoint=ENDPOINT, credential=_credential())
        # agents.create_version is the call the OneAgent Foundry sensor instruments.
        agent = client.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(
                model=MODEL,
                instructions=f"You are a haiku poet. Write haikus about {topic}.",
                temperature=1.0,
                top_p=1.0,
            ),
        )
        return f"created agent {agent.name} version {agent.version}\n"

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
