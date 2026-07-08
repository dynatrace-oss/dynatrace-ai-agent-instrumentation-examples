import asyncio
import os
from groq import Groq
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MODEL: str = os.environ.get("MODEL", "llama-3.1-8b-instant")

app = FastAPI(title="groq-oneagent")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def _call() -> str:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Write a haiku."}],
        )
        return response.choices[0].message.content

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
