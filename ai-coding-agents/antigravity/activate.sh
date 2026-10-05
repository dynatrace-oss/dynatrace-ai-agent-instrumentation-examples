#!/usr/bin/env bash
# Source this file (do NOT execute it) to export the Antigravity demo env vars:
#   cp .env.example .env && source activate.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in your credentials."
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck source=.env
source "$SCRIPT_DIR/.env"
set +a

if [ -z "$DT_API_TOKEN" ] || [ -z "$DT_OTEL_ENDPOINT" ]; then
  echo "ERROR: DT_API_TOKEN and DT_OTEL_ENDPOINT must be set in .env"
  return 1 2>/dev/null || exit 1
fi

# Normalise endpoint: strip trailing signal-specific path segments
for _suffix in "/v1/traces" "/v1/metrics" "/v1/logs"; do
  if [[ "$DT_OTEL_ENDPOINT" == *"$_suffix" ]]; then
    DT_OTEL_ENDPOINT="${DT_OTEL_ENDPOINT%$_suffix}"
  fi
done
export DT_OTEL_ENDPOINT

export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-antigravity}"
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_ENDPOINT="$DT_OTEL_ENDPOINT"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token ${DT_API_TOKEN}"

# Dynatrace requires delta temporality for metrics
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta

echo "Antigravity telemetry configured for Dynatrace:"
echo "  Service  : ${OTEL_SERVICE_NAME}"
echo "  Endpoint : ${OTEL_EXPORTER_OTLP_ENDPOINT}"
echo ""
echo "Run 'make run' to execute the agent, or 'python3 test_connection.py' to check transport."
