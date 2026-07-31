# LangGraph + Bedrock + Dynatrace

This sample instruments a [LangGraph](https://langchain-ai.github.io/langgraph/) agent backed by **AWS Bedrock** with Dynatrace using [OpenLLMetry](https://github.com/traceloop/openllmetry) (Traceloop SDK), routed through a [Dynatrace OpenTelemetry Collector](https://github.com/Dynatrace/dynatrace-otel-collector).

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Builds a minimal LangGraph state graph with a single `write_haiku` node that calls AWS Bedrock via `langchain_aws.ChatBedrock`
- Exports traces and metrics via OTLP HTTP to a local Dynatrace Collector, which forwards them to Dynatrace

The Traceloop SDK auto-instruments LangChain and LangGraph, so each request produces a distributed trace covering the graph run and the underlying LLM call, with token usage and cost captured as metrics.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- Docker (to run the Dynatrace Collector)
- A Dynatrace API token with `openTelemetryTrace.ingest` and `metrics.ingest`
- AWS credentials with Bedrock access (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`, or an IAM role)
- The target Bedrock model enabled in your AWS account

## Environment

Copy `.env.sample` to `.env` and fill in the values:

```env
DT_ENDPOINT=https://<tenant>.live.dynatrace.com
DT_API_TOKEN=dt0c01....

AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
```

AWS credentials are read from the standard AWS credential chain (environment variables, `~/.aws/credentials`, IAM role). You can add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` to `.env` if needed.

## Install and run

```bash
cd langgraph/opentelemetry/bedrock
make install
make run
```

Then in a second terminal:

```bash
make request
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv and install dependencies via uv |
| `make run` | Start the collector and the FastAPI app on port 8000 |
| `make request` | POST /haiku with a topic |
| `make stop` | Stop and remove the collector container |
| `make logs` | Tail collector logs |

## Dynatrace views

After a few minutes, refresh the Dynatrace views and you should see data being populated.

| View | What to look for |
|------|-----------------|
| **Distributed Tracing** | Filter by `service.name = langgraph-bedrock` |
| **AI Observability** | Token usage, latency, and model per request |

In the **AI Observability** app you can filter by service or model to explore token usage, cost breakdown, and latency across your graph runs. The **Agents topology** view shows how the `langgraph-bedrock` agent, the `aws.bedrock` provider, and the LLM model connect.
