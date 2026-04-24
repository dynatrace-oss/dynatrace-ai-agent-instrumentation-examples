#!/bin/bash
# Setup script for OpenCode OTEL telemetry with Dynatrace
# Usage: source setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in your credentials."
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.env"
set +a

if [ -z "$DT_API_TOKEN" ] || [ -z "$DT_OTEL_ENDPOINT" ]; then
  echo "ERROR: DT_API_TOKEN and DT_OTEL_ENDPOINT must be set in .env"
  return 1 2>/dev/null || exit 1
fi

# OpenCode reads these standard OTel env vars
export OTEL_EXPORTER_OTLP_ENDPOINT="$DT_OTEL_ENDPOINT"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $DT_API_TOKEN"

# Optional: enrich spans with team/environment context
# export OTEL_RESOURCE_ATTRIBUTES="service.namespace=myteam,environment=production"

echo "OpenCode telemetry configured for Dynatrace:"
echo "  Endpoint : $DT_OTEL_ENDPOINT"
echo "  Traces   : HTTP/protobuf (direct to Dynatrace)"
echo "  Logs     : HTTP/JSON (route via OpenTelemetry Collector for Dynatrace)"
echo ""
echo "Run 'opencode' to start a session with telemetry enabled."
