# n8n + Dynatrace
This sample instruments n8n workflows with Dynatrace using OpenLLMetry, routed through an OpenTelemetry Collector that captures Metrics, Traces and Logs and do the required tagging and enrichments for full discovery and granularity in Dynatrace.

## What this sample does

- Runs an `OTEL Collector` that captures b8b self-hosted instance telemetry
- Exports **traces** and **metrics** and **logs** directly to Dynatrace via OTLP HTTP
- Emits `Workflow Traces`, `LLM Usage`, `Instance and Execution Metrics` out of the box
  
## How it works

- The n8n self-instruments via OTel natively.
- 
## Prerequisites

## Environment

## Dynatrace AI Observability views

## OTLP signals exported
