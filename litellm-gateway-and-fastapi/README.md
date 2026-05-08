## LiteLLM Gateway and FastAPI Observability

This folder contains two examples for instrumenting LLM gateway traffic with OpenTelemetry and routing signals to Dynatrace.

Both examples use the [Traceloop SDK](https://www.traceloop.com/docs) for LLM-specific semantic conventions and a local OpenTelemetry Collector to forward gRPC-encoded signals to Dynatrace's OTLP HTTP endpoint.

| Example | Description |
|---|---|
| [fastapi-instrumentation](./fastapi-instrumentation/) | Custom FastAPI app using LiteLLM as an LLM router — full traces, custom metrics, and correlated logs |
| [litellm-gateway-with-instrumentation](./litellm-gateway-with-instrumentation/) | LiteLLM's built-in proxy server instrumented via Traceloop and FastAPI auto-instrumentation |

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

Both examples forward to a local collector over gRPC. Use the following minimal collector config:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  otlphttp:
    endpoint: https://<YOUR_ENV_ID>.live.dynatrace.com/api/v2/otlp
    headers:
      Authorization: "Api-Token <YOUR_DT_TOKEN>"

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlphttp]
    metrics:
      receivers: [otlp]
      exporters: [otlphttp]
    logs:
      receivers: [otlp]
      exporters: [otlphttp]
```
