import asyncio
import os
import haystack.tracing
from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import AzureOpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

# Disable Haystack's internal tracer — OneAgent instruments Pipeline.run directly
# and the two tracers conflict, causing a RuntimeError on context manager exit.
haystack.tracing.disable_tracing()

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/haiku", response_class=PlainTextResponse)
async def haiku() -> str:
    generator = AzureOpenAIChatGenerator(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "genai-demo"),
        api_key=Secret.from_env_var("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-07-01-preview"),
    )

    def _call() -> str:
        pipeline = Pipeline()
        pipeline.add_component("prompt", ChatPromptBuilder(template=[ChatMessage.from_user("Write a haiku about nature.")]))
        pipeline.add_component("llm", generator)
        pipeline.connect("prompt.prompt", "llm.messages")
        result = pipeline.run({})
        return result["llm"]["replies"][0].text

    return await asyncio.to_thread(_call)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
