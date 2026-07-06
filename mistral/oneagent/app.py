import os
from mistralai.client import Mistral
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MODEL: str = os.environ.get("MODEL", "mistral-small-latest")

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    import asyncio
    kwargs = {"api_key": os.getenv("MISTRAL_API_KEY")}
    # MISTRAL_BASE_URL lets the e2e suite point the SDK at a local mock when no
    # real MISTRAL_API_KEY is available; unset in normal use (defaults to the
    # public Mistral API).
    base_url = os.getenv("MISTRAL_BASE_URL")
    if base_url:
        kwargs["server_url"] = base_url
    client = Mistral(**kwargs)

    def _call() -> str:
        response = client.chat.complete(
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
        )
        return response.choices[0].message.content

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
