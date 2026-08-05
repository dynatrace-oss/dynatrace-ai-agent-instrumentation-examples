import os

import openai
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from openai import Stream
from pydantic import BaseModel

MODEL: str = os.environ.get("MODEL", "gpt-4o")

app = FastAPI(title="openai-oneagent")


class HaikuRequest(BaseModel):
    topic: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku(body: HaikuRequest | None = None) -> str:
    import asyncio
    api_version = os.getenv("OPENAI_API_VERSION")
    if api_version:
        client = openai.AzureOpenAI(
            azure_endpoint=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_version=api_version,
        )
    else:
        client = openai.OpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    topic = body.topic if body else None
    user_message = f"Write a haiku about {topic}." if topic else "Write a haiku."

    def _call() -> str:
        try:
            response: Stream = client.chat.completions.create(  # type: ignore[assignment]
                model=MODEL,
                messages=[{"role": "user", "content": user_message}],
                max_completion_tokens=20,
                stream=True,
            )
            result = ""
            for chunk in response:
                if chunk.choices and (content := chunk.choices[0].delta.content):
                    result += content
            return result
        except openai.BadRequestError as exc:
            if exc.code == "content_filter":
                return f"[content filter triggered] {exc.message}"
            raise

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
