import os
from typing import Optional

import litellm
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# LiteLLM routes "groq/<model>" to Groq's OpenAI-compatible API.
MODEL: str = os.environ.get("MODEL") or "llama-3.1-8b-instant"
API_BASE: Optional[str] = os.environ.get("GROQ_API_BASE") or None

app = FastAPI(title="litellm-oneagent")


class HaikuRequest(BaseModel):
    topic: str = "observability"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku(request: Optional[HaikuRequest] = None) -> str:
    topic = request.topic if request else "observability"
    response = await litellm.acompletion(
        model=f"groq/{MODEL}",
        api_base=API_BASE,
        messages=[
            {"role": "system", "content": "You are a haiku poet."},
            {"role": "user", "content": f"Write a haiku about {topic}."},
        ],
        max_tokens=2000,
        temperature=1.0,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
