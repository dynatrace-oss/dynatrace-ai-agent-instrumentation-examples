import asyncio
import os
from ollama import Client

_web_app_info = None


def setup_instrumentation() -> None:
    global _web_app_info
    import oneagent
    oneagent.initialize()
    sdk = oneagent.get_sdk()
    _web_app_info = sdk.create_web_application_info(
        virtual_host="localhost",
        application_id=os.environ.get("OTEL_SERVICE_NAME", "ollama/oneagent"),
        context_root="/",
    )


setup_instrumentation()
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MODEL: str = os.environ.get("MODEL", "llama3.2")
OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    client = Client(host=OLLAMA_HOST)

    def _call() -> str:
        response = client.chat(
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
        )
        return response.message.content

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
