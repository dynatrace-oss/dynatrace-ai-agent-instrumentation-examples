# LangChain + OneAgent (Gemini and Claude)

This sample traces a LangChain agentic-RAG workflow with Dynatrace using **OneAgent auto-instrumentation** only. No OpenTelemetry SDK or collector is involved.

OneAgent's LangChain sensor records the call structure (workflow, task, agent, tool and retrieval spans). Model and token usage come from the provider SDK sensors underneath LangChain:

| LangChain model | Provider SDK | OneAgent sensor |
|---|---|---|
| `ChatGoogleGenerativeAI`, `GoogleGenerativeAIEmbeddings` (`langchain-google-genai`) | `google-genai` | Google GenAI |
| `ChatAnthropic` (`langchain-anthropic`) | `anthropic` | Anthropic |

> The LangChain sensor is not experimental, but the Google GenAI and Anthropic sensors are. Enable them in your Dynatrace settings, otherwise spans show the LangChain structure without model or token attributes.

The same sensors cover the Vertex AI variants (`ChatGoogleGenerativeAI` with `vertexai=True`, `ChatAnthropicVertex`), because those use the same `google-genai` and `anthropic` SDKs with a different endpoint.

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Indexes a small in-memory haiku guide with Gemini embeddings at startup
- Runs one LangChain workflow per request: the model calls a `search_haiku_guide` tool (vector-store retriever), then writes the haiku from the result
- Does the same with Claude when `ANTHROPIC_API_KEY` is set (optional, not asserted in CI)

The e2e test asserts this trace (the nesting of the Google GenAI spans is not asserted):

```
workflow   haiku_workflow                    [LangChain]
  task     prompt template and output parser [LangChain]
  agent    model call, turns 1 and 2         [LangChain]
    chat   model and token usage             [Google GenAI]
  tool     search_haiku_guide                [LangChain]
    retrieval                                [LangChain]
      embeddings  query embedding            [Google GenAI]
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Dynatrace OneAgent installed on the host, with the LangChain and Google GenAI sensors enabled (and Anthropic, if used)
- A Gemini API key; optionally an Anthropic API key

## Environment

```env
GOOGLE_API_KEY=...
# Optional
ANTHROPIC_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
CLAUDE_MODEL=claude-haiku-5-5
```

## Install and run

```bash
cd langchain/oneagent
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
| `make install` | Install dependencies via uv |
| `make run` | Start the FastAPI app on port 8000 |
| `make request` | POST /haiku with a sample topic |
| `make build` / `make push` | Build / push the container image |

## Dynatrace views

Open the **AI Observability** app and filter by `service.name = langchain/oneagent` to see the workflow trace with its tool and retrieval steps, and the model, token usage, and latency for each call.
