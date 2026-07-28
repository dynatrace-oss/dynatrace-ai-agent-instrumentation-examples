import os
import openai
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MODEL: str = os.environ.get("MODEL", "gpt-4o")

app = FastAPI(title="openai-oneagent")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
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

    def _call() -> str:
        # Non-streaming: OneAgent's Python OpenAI sensor only fully captures
        # gen_ai.response.model and token usage in non-streaming mode (see
        # test/e2e/sdk-analysis/openai-oneagent.md). No behavior change here —
        # the streaming loop just assembled all chunks synchronously anyway.
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
            max_completion_tokens=20,
            stream=False,
        )
        return response.choices[0].message.content or ""

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

