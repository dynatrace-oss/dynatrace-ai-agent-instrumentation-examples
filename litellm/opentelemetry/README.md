## LiteLLM Gateway and FastAPI Observability

This folder contains two examples for instrumenting LLM gateway traffic with OpenTelemetry and routing signals to Dynatrace.

Both examples use [OpenInference](https://github.com/Arize-ai/openinference) (`openinference-instrumentation-litellm`) with OTel GenAI semantic conventions enabled (`enable_genai_semconv=True`) for LLM spans, and a local OpenTelemetry Collector to forward signals to Dynatrace's OTLP HTTP endpoint. OpenInference emits spans only; the Collector derives the OTel GenAI client metrics (`gen_ai.client.token.usage`, `gen_ai.client.operation.duration`) from them.

> [!IMPORTANT]
> The FastAPI example also sends custom metrics and logs over gRPC. Two settings are required for them to reach Dynatrace:
> - The gRPC metric and log exporters target the local collector's **plaintext** gRPC port (4317), so they are created with `insecure=True`; without it the TLS handshake fails and metrics/logs never leave the app.
> - Dynatrace OTLP metric ingest accepts **delta** temporality only (cumulative is rejected with HTTP 400), so the app sets `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`.

The Dynatrace API token needs the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, and **`logs.ingest`** scopes.

| Example | Description |
|---|---|
| [fastapi-instrumentation](./fastapi-instrumentation/) | Custom FastAPI app using LiteLLM as an LLM router; full traces, custom metrics, and correlated logs |
| [litellm-gateway-with-instrumentation](./litellm-gateway-with-instrumentation/) | LiteLLM's built-in proxy server instrumented via OpenInference and FastAPI auto-instrumentation |

> [!TIP]
> For Dynatrace setup instructions, API token scopes, and advanced configuration, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

## Architecture

```
Client → FastAPI / LiteLLM proxy → LLM providers (xAI, Groq, Anthropic, Ollama)
                    ↓
           OTel Collector (localhost:4317 gRPC)
                    ↓
         Dynatrace OTLP HTTP endpoint
```

### OTel Collector config

The shared [`otel-collector-config.yaml`](./otel-collector-config.yaml) fills `gen_ai.*` gaps from OpenInference's legacy attributes, then drops `llm.*`/`openinference.*`, and derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from LLM spans. It needs the [Bindplane Distro for OpenTelemetry](https://github.com/observIQ/bindplane-otel-collector) for the `signal_to_metrics` connector. Each example's `make run` starts it.
