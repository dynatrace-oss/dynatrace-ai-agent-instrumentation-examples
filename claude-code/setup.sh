#!/bin/bash
# Setup script for Claude Code OTEL telemetry with Dynatrace
# Usage: source setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in your credentials."
  return 1 2>/dev/null || exit 1
fi

# Load .env variables
set -a
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.env"
set +a

if [ -z "$DT_API_TOKEN" ] || [ -z "$DT_OTEL_ENDPOINT" ]; then
  echo "ERROR: DT_API_TOKEN and DT_OTEL_ENDPOINT must be set in .env"
  return 1 2>/dev/null || exit 1
fi

# Enable Claude Code telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# Use OTLP HTTP/protobuf (required for Dynatrace)
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Dynatrace OTLP endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT="$DT_OTEL_ENDPOINT"

# Dynatrace authentication header
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $DT_API_TOKEN"

# Dynatrace requires delta temporality for metrics
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta

# Optional: shorten export intervals during setup/debugging
# export OTEL_METRIC_EXPORT_INTERVAL=10000   # 10s (default: 60000ms)
# export OTEL_LOGS_EXPORT_INTERVAL=5000      # 5s  (default: 5000ms)

# Optional: include tool details and user prompts in events
# export OTEL_LOG_TOOL_DETAILS=1
export OTEL_LOG_USER_PROMPTS=1

echo "Claude Code telemetry configured for Dynatrace:"
echo "  Endpoint : $DT_OTEL_ENDPOINT"
echo "  Metrics  : $OTEL_METRICS_EXPORTER (${OTEL_EXPORTER_OTLP_PROTOCOL})"
echo "  Logs     : $OTEL_LOGS_EXPORTER (${OTEL_EXPORTER_OTLP_PROTOCOL})"
echo ""
echo "Run 'claude' to start a session with telemetry enabled."
