## OpenAI Agent SDK


This example contains a demo of a Customer Service Agent interface built on top of the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/). The original example code can be found in the [openai-cs-agents-demo](https://github.com/openai/openai-cs-agents-demo) GitHub repo.

![Tracing](./dynatrace.png)

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).


The Dynatrace full-stack observability platform combined with Traceloop's OpenLLMetry OpenTelemetry SDK can seamlessly provide comprehensive insights into Large Language Models (LLMs) in production environments. By observing AI models, businesses can make informed decisions, optimize performance, and ensure compliance with emerging AI regulations.

Enabling and configuring OpenLLMetry is as easy as to copy/paste this snippet into your [`api.py`](./python-backend/api.py) file.

```python
os.environ['TRACELOOP_TELEMETRY'] = "false"
os.environ['OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE'] = "delta"

def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception as e:
        print("No token was provided")
        print(e)
        return ""

token = read_secret("dynatrace_otel") # read your DT API token from a file in /etc/secrets/dynatrace_otel
headers = {"Authorization": f"Api-Token {token}"}
from traceloop.sdk import Traceloop
Traceloop.init(
    app_name="openai-cs-agents",
    api_endpoint="https://wkf10640.live.dynatrace.com/api/v2/otlp", # configure your DT tenant here
    disable_batch=True,
    headers=headers,
    should_enrich_metrics=True,
)
```


## How to use

### Setting your OpenAI API key

You can set your [Azure]OpenAI API key in your environment variables by running the following command in your terminal:

```bash
export OPENAI_API_KEY=your_api_key
```

```bash
export AZURE_OPENAI_API_KEY=your_api_key
export AZURE_OPENAI_API_VERSION='2024-08-01-preview'
export AZURE_OPENAI_ENDPOINT=your_endpoint
export AZURE_OPENAI_DEPLOYMENT=your_deployment
```


Alternatively, you can set the `OPENAI` and/or `AZURE` environment variables in an `.env` file at the root of the `python-backend` folder. You will need to install the `python-dotenv` package to load the environment variables from the `.env` file.

### Install dependencies

Install the dependencies for the backend by running the following commands:

```bash
cd python-backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For the UI, you can run:

```bash
cd ui
npm install
```

### Run the app

From the `ui` folder, run:

```bash
npm run dev
```

The frontend will be available at: [http://localhost:3000](http://localhost:3000)

This command will also start the backend.

![Demo Screenshot](screenshot.jpg)