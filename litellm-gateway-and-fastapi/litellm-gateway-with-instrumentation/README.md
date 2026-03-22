# LiteLLM  Gateway 

This is the basic implementation of LiteLLM Gateway instrumented with Traceloop.
with a configuration file that includes two LLMs and the Admin UI enabled.
```
import uvicorn
from litellm.proxy.proxy_server import app

FastAPIInstrumentor.instrument_app(app)

# Note: workers=1 only — Traceloop.init() only runs in this process
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4000, log_level="debug")

```

## Get Started 

```
cd litellm-gateway-with-instrumentation

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
source .env

```






```
model_list:
  - model_name: ollama-llama3.2 
    litellm_params: # all params accepted by litellm.completion() - https://docs.litellm.ai/docs/completion/input
      model: ollama-llama3.2:latest  ### MODEL NAME sent to `litellm.completion()` ###
      api_base: OLLAMA_BASE_URL=http://localhost:11434
      api_key: "NO_KEY" # does os.getenv("AZURE_API_KEY_EU")
      rpm: 6      # [OPTIONAL] Rate limit for this deployment: in requests per minute (rpm)
  - model_name: anthropic
    litellm_params:
      model: anthropic/claude-sonnet-4-6
 ```
