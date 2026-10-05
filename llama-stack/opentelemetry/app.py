import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from llama_stack.core.library_client import AsyncLlamaStackAsLibraryClient

MODEL: str = os.environ.get("MODEL", "llama3.2")

app = FastAPI(title="llama-stack-opentelemetry")

# Llama Stack runs in-process (library mode); inference goes to Ollama.
client = AsyncLlamaStackAsLibraryClient(str(Path(__file__).parent / "config.yaml"))


@app.on_event("startup")
async def startup() -> None:
    await client.initialize()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    response = await client.chat.completions.create(
        model=f"ollama/{MODEL}",
        messages=[{"role": "user", "content": "Write a haiku."}],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
