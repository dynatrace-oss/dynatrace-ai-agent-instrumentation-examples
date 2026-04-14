#!/bin/bash
# Setup script for OpenClaw OTEL telemetry with Dynatrace
# Usage: ./setup.sh <ENDPOINT> <API_TOKEN>
#
# Example:
#   ./setup.sh https://abc12345.live.dynatrace.com/api/v2/otlp dt0c01.XXXXXXXX.YYYYYYYY

if [ $# -lt 2 ]; then
  echo "Usage: ./setup.sh <ENDPOINT> <API_TOKEN>"
  echo ""
  echo "  ENDPOINT   Dynatrace OTLP endpoint (e.g. https://<env-id>.live.dynatrace.com/api/v2/otlp)"
  echo "  API_TOKEN  Dynatrace API token with openTelemetryTrace.ingest scope"
  exit 1
fi

ENDPOINT="$1"
API_TOKEN="$2"

# Configure OpenClaw diagnostics-otel plugin via CLI
echo "Configuring OpenClaw diagnostics-otel plugin …"
openclaw config set diagnostics.enabled true
openclaw config set diagnostics.otel.enabled true
openclaw config set diagnostics.otel.traces true
openclaw config set diagnostics.otel.metrics true
openclaw config set diagnostics.otel.logs true
openclaw config set diagnostics.otel.protocol http/protobuf
openclaw config set diagnostics.otel.endpoint "$ENDPOINT"
openclaw config set diagnostics.otel.headers "{\"Authorization\":\"Api-Token $API_TOKEN\"}"
openclaw config set diagnostics.otel.serviceName "openclaw-gateway"

# Write OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta to ~/.openclaw/.env
# Dynatrace requires delta temporality for metrics (mandatory)
OPENCLAW_ENV="$HOME/.openclaw/.env"
mkdir -p "$(dirname "$OPENCLAW_ENV")"
if grep -q "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE" "$OPENCLAW_ENV" 2>/dev/null; then
  sed -i 's/^OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=.*/OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta/' "$OPENCLAW_ENV"
else
  echo "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta" >> "$OPENCLAW_ENV"
fi

echo ""
echo "OpenClaw telemetry configured for Dynatrace:"
echo "  Endpoint : $ENDPOINT"
echo "  Protocol : http/protobuf"
echo "  Env file : $OPENCLAW_ENV"
echo ""
echo "Run 'openclaw start' to launch the gateway with telemetry enabled."
