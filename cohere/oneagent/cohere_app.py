import asyncio
import os
import cohere

_web_app_info = None


def setup_instrumentation() -> None:
    global _web_app_info
    import oneagent
    oneagent.initialize()
    sdk = oneagent.get_sdk()
    _web_app_info = sdk.create_web_application_info(
        virtual_host="localhost",
        application_id=os.environ.get("OTEL_SERVICE_NAME", "cohere/oneagent"),
        context_root="/",
    )


setup_instrumentation()
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MODEL: str = os.environ.get("MODEL", "command-r-08-2024")

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    co = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    def _call() -> str:
        response = co.chat(
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
        )
        return response.message.content[0].text

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
