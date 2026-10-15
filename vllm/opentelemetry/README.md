# vLLM built-in OpenTelemetry tracing: overhead check

Measures how much vLLM's own OpenTelemetry tracing costs in token throughput, and how many spans it emits per request.

vLLM can export one span per request (`--otlp-traces-endpoint`). It joins the caller's trace when the request carries a W3C `traceparent` header, so a gateway or agent span links to the inference span. `--collect-detailed-traces` adds model and worker timing, which vLLM documents as possibly costly and blocking.

The benchmark compares four setups against the same model:

| Label | vLLM flags | Sampled share of requests |
|---|---|---|
| `off` | none | n/a |
| `traced-1.0` | `--otlp-traces-endpoint` | 100% |
| `traced-0.1` | `--otlp-traces-endpoint` | 10% (parent-based, via the `traceparent` sampled flag) |
| `detailed-1.0` | `--otlp-traces-endpoint --collect-detailed-traces all` | 100% |

Spans go to `span_sink.py`, a small OTLP/HTTP receiver that counts spans per trace. It stands in for a node-local collector, so the network cost is close to zero.

## Prerequisites

- Docker (the `vllm/vllm-openai-cpu` image runs on arm64 and amd64)
- [uv](https://docs.astral.sh/uv/)
- About 4 GB free memory for the 0.5B model

## Run

```bash
make install
make sink        # terminal 1
make compare     # terminal 2
```

`make compare` prints one JSON line per setup with `output_tokens_per_s`, `mean_latency_s`, and `spans_per_trace`. Tune load with `REQUESTS`, `CONCURRENCY`, and `MAX_TOKENS`.

To run one setup at a time:

```bash
make run MODE=detailed
make bench MODE=detailed
```

## Results

vLLM 0.31.0 CPU image, Qwen2.5-0.5B-Instruct, 128 requests at concurrency 8, 64 output tokens each, on a 6-core Apple silicon laptop:

| Label | Output tokens/s | Mean latency | Spans per traced request |
|---|---|---|---|
| `off` | 75.2 | 6.81 s | n/a |
| `traced-1.0` | 75.4 | 6.79 s | 1 (`llm_request`) |
| `traced-0.1` | 73.7 | 6.95 s | 1 (18 of 128 requests traced) |
| `detailed-1.0` | 75.2 | 6.81 s | 1 (`llm_request`) |

All differences are within run-to-run noise (about 2%). vLLM emits one span per request and exports it from a background thread, so tracing doesn't slow token generation here. Parent-based sampling works without vLLM configuration: only requests with a sampled `traceparent` get a span, and that span joins the caller's trace.

Recommended setup for a high-throughput path:

- Enable `--otlp-traces-endpoint`; leave `--collect-detailed-traces` off, since vLLM documents it as possibly costly and blocking.
- Head-sample at the gateway or agent with `OTEL_TRACES_SAMPLER=parentbased_traceidratio`; vLLM follows the caller's decision.
- Export to a node-local collector for batching and routing.
- Keep Prometheus scraping for always-on metrics (TTFT, inter-token latency, KV cache usage).

## Limits

- The CPU image shows relative overhead only. GPU decode is much faster, so any per-step cost (such as the timing that `--collect-detailed-traces` adds) takes a larger share there. Rerun on the target GPU node before quoting numbers.
- Without a `traceparent` header, vLLM samples by the SDK default (`parentbased_always_on`), so every request gets traced. Set `OTEL_TRACES_SAMPLER` on the vLLM container if callers don't send trace context.
