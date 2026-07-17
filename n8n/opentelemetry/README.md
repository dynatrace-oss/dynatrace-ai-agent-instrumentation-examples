# n8n + Dynatrace
This sample instruments n8n workflows with Dynatrace using OpenTelemetry, routed through an OpenTelemetry Collector that captures Metrics, Traces and Logs and do the required tagging on Metrics and Logs, and transformation on Traces for full discovery and granularity in Dynatrace, with Ready made Dashboards for instant value.

## What this sample does

- Installs a `Self hosted n8n` on Docker 
- Enables n8n OpenTelemetry
- Runs an `OTEL Collector` on Docker that captures n8n self-hosted instance telemetry
- Emits `Workflow Traces`, `LLM Usage`, `Instance and Execution Metrics` from n8n directly to Dynatrace via OTLP HTTP
- Dashboards to visualize Workflows Health and Performance, LLM Usage and Audit Logs
  
## How it works

- The n8n self-instruments via OTel natively.
- Telemetry will be routed through a OTEL Collector, that is configured to emit, enrich, associate and retransform the traces, metrics, and logs to be properly ingested by Dynatrace
- Everything will work out of the box at this point, the guide will provide the necessary logs parsing queries and Dashbaords to get you instant value

## How to use

### Prerequisites
- [Self-Hosted n8n](https://docs.n8n.io/deploy/host-n8n) - Free Community Edition is fully compatabile
- A running [OpenTelemetry Collector](#opentelemetry-collector) forwarding to Dynatrace
- A Dynatrace environment with an API token that has the **`openpipeline:traces:ingest`** and **`openpipeline:metrics:ingest`** and **`openpipeline:logs:ingest`** scopes

### Environment
Copy `.env.sample` to `.env` and fill in the values at the end:

```env
# WARNING
# This is a sample file only. Rename to .env
# DO NOT STORE your .env file in Git!
#
# git clone https://github.com/n8n-io/n8n-hosting
# cd n8n-hosting/n8n-hosting/docker-compose/withPostgres
# docker compose up -d
#
POSTGRES_USER=admin
POSTGRES_PASSWORD=dynatrace
POSTGRES_DB=n8n

POSTGRES_NON_ROOT_USER=admin
POSTGRES_NON_ROOT_PASSWORD=dynatrace
# Enable metrics AG
# https://docs.n8n.io/hosting/configuration/environment-variables/endpoints/
N8N_METRICS=true
#N8N_METRICS_INCLUDE_CACHE_METRICS=true
N8N_METRICS_INCLUDE_MESSAGE_EVENT_BUS_METRICS=true
N8N_METRICS_INCLUDE_WORKFLOW_ID_LABEL=true
N8N_METRICS_INCLUDE_NODE_TYPE_LABEL=true
N8N_METRICS_INCLUDE_CREDENTIAL_TYPE_LABEL=true
N8N_METRICS_INCLUDE_API_ENDPOINTS=true
N8N_METRICS_INCLUDE_API_PATH_LABEL=true
N8N_METRICS_INCLUDE_API_METHOD_LABEL=true
N8N_METRICS_INCLUDE_API_STATUS_CODE_LABEL=true
#N8N_METRICS_INCLUDE_QUEUE_METRICS=true
#N8N_METRICS_QUEUE_METRICS_INTERVAL=true

# Scrape logs and metrics to Dynatrace
# Replace abc12345 below with your environment ID
# API Token requires these permissions:
# "ingest metrics" and "ingest logs" and "ingest traces"
DT_ENVIRONMENT_URL=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.******.******
#The Service Name that will appear in Dynatrace Services (has to be the same service name set in n8n Opentelemtry settings)
DT_SERVICE_NAME=n8n

```

### Observe the OTEL Collector Processor Configuration

Notable observations that make the instrumentation work correctly in Dynatrace:
- **resource/n8n_logs**
  - Sets the `service.name` attribute to associate logs with the corresponding discovered service in Dynatrace.
- **resource/n8n_metrics**
  - Sets the `service.name` attribute to associate metrics with the corresponding discovered service in Dynatrace.
- **transform/n8n**
  - Sets the `workflow.execute` parent span as the root span and assigns it the `server` span kind, making the n8n service discoverable in Dynatrace.
  - Renames the default `workflow.execute` parent spans to `workflow.execute/[workflow.id]`, providing granular service endpoints for each workflow.
  - Renames the default `node.execute` child spans to `node.execute/[node.type]`, creating meaningful inner span names that clearly represent the individual node types executed within a workflow.

```yaml
processors:
  batch:
    send_batch_size: 500
    timeout: 2s
  cumulativetodelta:
  # --- To associate the logs with the n8n discovered Service in Dyantrace ---
  resource/n8n_logs:
    attributes:
      - action: insert
        key: service.name
        value: ${env:DT_SERVICE_NAME}
  # --- To associate the Metrics with the n8n discovered Service in Dyantrace ---
  resource/n8n_metrics:
    attributes:
      - action: upsert
        key: service.name
        value: ${env:DT_SERVICE_NAME}
  transform/n8n:
    trace_statements:
      - context: span
        statements:
          # --- set workflow.execute parent span as root and type server to make the n8n service discoverable in dynatrace ---
          - set(kind, 2)
            where IsMatch(name, "^workflow\\.execute")
            and resource.attributes["service.name"] == "${env:DT_SERVICE_NAME}"
          - set(attributes["request.is_root_span"], true)
            where IsMatch(name, "^workflow\\.execute")
            and resource.attributes["service.name"] == "${env:DT_SERVICE_NAME}"
          # ---default workflow.execute parent spans rename to workflow.execute/[workflow.id] ---
          - set(name, Concat(["workflow.execute/", attributes["n8n.workflow.id"]], ""))
            where IsMatch(name, "^workflow\\.execute")
            and resource.attributes["service.name"] == "${env:DT_SERVICE_NAME}"
            and attributes["n8n.workflow.id"] != nil
          # --- default node.execute inner spans rename to node.execute/[node.type] ---
          - set(name, Concat(["node.execute/", attributes["n8n.node.type"]], ""))
            where IsMatch(name, "^node\\.execute$")
            and resource.attributes["service.name"] == "${env:DT_SERVICE_NAME}"
            and attributes["n8n.node.type"] != nil
```


### Install and run
 ```bash
docker compose up
```

### n8n Configuration

### n8n import sample workflow

### Verify in Dynatrace

```dql
fetch spans, from:now()-1h
| filter service.name == "n8n" //replace with the service name you configured in the n8n settings
| sort timestamp desc
| limit 50
```

## Dynatrace AI Observability views
- **Services**
  - Service Discovered
  - Associated Logs
  - Associated 
- **Dashboard**
  - Associated 
- **Logs**
  - DQL
- **Metrics**
  - Explorer

## OTLP signals exported

