import os
import openai

_web_app_info = None


def setup_instrumentation() -> None:
    global _web_app_info
    import oneagent
    oneagent.initialize()
    sdk = oneagent.get_sdk()
    _web_app_info = sdk.create_web_application_info(
        virtual_host="localhost",
        application_id=os.environ.get("OTEL_SERVICE_NAME", "openai/oneagent"),
        context_root="/",
    )


setup_instrumentation()
from openai import Stream
from openai.types.chat import ChatCompletionChunk
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MODEL: str = os.environ.get("MODEL", "gpt-4o")

app = FastAPI()


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
        response: Stream[ChatCompletionChunk] = client.chat.completions.create(  # type: ignore[assignment]
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
            max_completion_tokens=20,
            stream=True,
        )
        result = ""
        for chunk in response:
            if chunk.choices and (content := chunk.choices[0].delta.content):
                result += content
        return result

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

