# OpenInference + Dynatrace — Haiku tracing tutorial

![OpenInference and Dynatrace](assets/openinference.png)

Generate a haiku with an LLM and send the OpenTelemetry trace into Dynatrace. This repository contains a small example application and instructions to run a local Dynatrace OpenTelemetry Collector that forwards traces into your Dynatrace tenant.

Nice and simple — write a haiku, trace the request, and see the trace in Dynatrace.

---

Table of contents
- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Create a Dynatrace access token](#create-a-dynatrace-access-token)
- [Start the Dynatrace OpenTelemetry Collector](#start-the-dynatrace-opentelemetry-collector)
- [(Optional) Configure custom OpenAI endpoints](#optional-configure-custom-openai-endpoints)
- [Run the application](#run-the-application)
- [Visualize the trace in Dynatrace](#visualize-the-trace-in-dynatrace)
- [Troubleshooting](#troubleshooting)

---

## What you'll build
A tiny demonstration that:
- Calls an LLM to generate a haiku (you may use the LLM API/provider of your choice).
- Produces OpenTelemetry traces for the LLM request.
- Forwards traces to Dynatrace via the Dynatrace OpenTelemetry Collector running locally in Docker.
- Lets you view the generated distributed trace in the Dynatrace UI.

---

## Prerequisites

- A Dynatrace tenant. Start a trial (if you don't have one) at: https://dt-url.net/trial
- Docker installed and running (we use the Dynatrace OTEL Collector container).
- Python 3.8+
- An OpenAI-compatible LLM endpoint or API key if you intend to run the LLM call locally.

Notes:
- Make a note of your Dynatrace tenant ID. The tenant ID is the first part of the tenant URL:
  - Example: in `https://abc12345.apps.dynatrace.com` the tenant ID is `abc12345`.

---

## Create a Dynatrace access token

1. In the Dynatrace web UI press `Ctrl + K`, search for **Access tokens**.
2. Create a new token and give it the permission:
   - `openTelemetryTrace.ingest`
3. Copy the token — you will export it into an environment variable below.

---

## Start the Dynatrace OpenTelemetry Collector

Prepare:
- Ensure you have an `otel-collector-config.yaml` in the repository root (this example mounts that file into the Docker container). The collector configuration should be tuned to forward traces to Dynatrace (your config may already be provided in the repo).

Set environment variables (example):

```bash
# Replace with your tenant ID (example abc12345)
export DT_ENDPOINT=https://abc12345.live.dynatrace.com
export DT_API_TOKEN=dt0c01.****.*****    # your access token created above
```

Why: the collector needs to know the Dynatrace ingest endpoint and the token to forward traces.

Run the collector (Linux/macOS):

```bash
docker run --rm -it \
  -v $(pwd)/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml \
  -p 4318:4318 \
  ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.44.0 \
  --config=/etc/otelcol/otel-collector-config.yaml
```

Run the collector (Windows CMD):

```cmd
docker run --rm -it ^
  -v %cd%/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml ^
  -p 4318:4318 ^
  ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.44.0 ^
  --config=/etc/otelcol/otel-collector-config.yaml
```

Notes:
- Port 4318 (the OpenTelemetry HTTP/OTLP port) is exposed so your app can send telemetry to the collector at `http://localhost:4318`.
- The commands bind an interactive terminal to the container so you can inspect logs/output as the collector runs.

---

## (Optional) Configure custom OpenAI endpoints
If you are using a custom OpenAI-compatible endpoint, set these environment variables:
```bash
export OPENAI_API_BASE=https://custom.endpoint.com/
export OPENAI_API_KEY=**********************
export MODEL=gpt-5-1
```
Adjust the example `MODEL` and keys for whichever provider or model you use.

---

## Run the application
This example app makes a single call (generate a haiku) and emits an OpenTelemetry trace to the local collector.

Start the app:

```bash
python app.py
```

What happens:
- The app calls your LLM endpoint to generate a haiku.
- The app emits an OTLP trace to the local collector at `http://localhost:4318`.
- The collector forwards the trace to your Dynatrace tenant using the `DT_ENDPOINT` and `DT_API_TOKEN`.

---

## Visualize the trace in Dynatrace

1. In Dynatrace press `Ctrl + K` and search for **Distributed tracing**.
2. Look for your trace (search by `service name == openinference`, trace ID, or timeframe).
3. Open the trace to inspect spans and attributes created by the application and the OTEL instrumentation.

![OpenInference](assets/openinference.png)

---

## Troubleshooting
- Collector not starting / Docker errors:
  - Confirm your `otel-collector-config.yaml` path is correct and readable by Docker.
  - Run `docker ps` to ensure the container is running.
  - Inspect container output (the Docker run above attaches stdout so you should see logs in the terminal).

- No traces appear in Dynatrace:
  - Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
  - Confirm the access token has `openTelemetryTrace.ingest` permission.
  - Confirm your app is sending to `http://localhost:4318` (the OTLP HTTP port).
  - Check the collector logs for errors when forwarding to Dynatrace.

- Port conflict:
  - Ensure nothing else is listening on `4318` locally. Use `ss -ltnp` or `netstat -an` to check.

- Authentication/authorization issues:
  - If the collector logs indicate a 401/403 when contacting Dynatrace, re-check the token and tenant URL.

If you hit a specific error, copy the relevant collector logs and the minimal steps to reproduce and open an issue.
