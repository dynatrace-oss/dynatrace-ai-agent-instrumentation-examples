

# Getting Traceloop to Auto-Instrument LiteLLM - No Manual Spans
The following is what I have been able to discover and test so far on the LiteLLM 
Instrumention. 


Here's the situation: Traceloop's OpenLLMetry does NOT have a native LiteLLM instrumentor. 
Its auto-instrumentation covers OpenAI, Anthropic, Cohere, Vertex, etc. directly — 
but LiteLLM is a proxy/router on top of those, and it's not in the supported auto-instrument list.


## There are Two Options

## Option A: 
### Use LiteLLM's Built-in OTEL Callback (Cleanest)

This is the right path when LiteLLM is your gateway. Just set the callback and point it at your OTLP endpoint — no manual spans needed at all:
```
python import litellm

from litellm.integrations.opentelemetry import OpenTelemetry as LiteLLMOTel
```

### This one line auto-instruments every litellm.completion() call**

litellm.callbacks = [LiteLLMOTel()]

You already have this in your main.py. The issue is you're also wrapping litellm.completion() manually in a with tracer.start_as_current_span(...) block. That's double-instrumentation — the LiteLLMOTel() callback already captures all the gen_ai.* attributes automatically. Your manual span block in chat_completions() can be deleted entirely.

``` Configure the built-in callback via env vars:
OTEL_EXPORTER=otlp_grpc
OTEL_ENDPOINT=http://localhost:4317
OTEL_HEADERS="api-key=your-traceloop-key"
```

## Option B:
### Use openinference-instrumentation-litellm

The openinference-instrumentation-litellm package implements OTel-compatible tracing for LiteLLM functions and is fully compatible with any OTLP collector. openinference It follows the standard OTel instrumentor pattern:
bashpip install openinference-instrumentation-litellm

```
python from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Wire it to your existing TracerProvider
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317")))

LiteLLMInstrumentor().instrument(tracer_provider=provider)
```

# Option One Implementation : Test Implementation 

After this, every litellm.completion() call is automatically traced — no with tracer.start_as_current_span(...) needed.
Cleaned-up main.py Using Option A

```
pythonimport litellm
import os
from litellm import ModelResponse
from litellm.integrations.opentelemetry import OpenTelemetry as LiteLLMOTel
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from traceloop.sdk import Traceloop
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

HTTPXClientInstrumentor().instrument()

TRACELOOP_BASE_URL = os.environ["TRACELOOP_BASE_URL"]

if os.environ.get("XAI_API_KEY"):
    litellm.xai_api_key = os.environ["XAI_API_KEY"]
if os.environ.get("GROQ_API_KEY"):
    litellm.groq_api_key = os.environ["GROQ_API_KEY"]

# LiteLLMOTel callback handles ALL gen_ai.* spans automatically
litellm.callbacks = [LiteLLMOTel()]

Traceloop.init(
    app_name="litellm-gateway",
    api_endpoint=TRACELOOP_BASE_URL,
    api_key="KEY",
    disable_batch=True,
)

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    kwargs = {"model": request.model, "messages": messages}
    if request.max_tokens is not None:
        kwargs["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature

    try:
        # LiteLLMOTel callback auto-creates the child span with all gen_ai.* attributes
        return litellm.completion(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```
