#!/usr/bin/env bash
#
# Install the openclaw-observability-plugin and wire it to a Dynatrace OTLP endpoint.
#
# Usage:
#   ./setup.sh https://<env-id>.live.dynatrace.com/api/v2/otlp <DT_API_TOKEN>
#
# The token must have the openTelemetryTrace.ingest, metrics.ingest, and logs.ingest scopes.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <dynatrace-otlp-endpoint> <dynatrace-api-token>" >&2
  exit 64
fi

OTLP_ENDPOINT="$1"
DT_TOKEN="$2"

PLUGIN_REPO="https://github.com/henrikrexed/openclaw-observability-plugin.git"
PLUGIN_ID="otel-observability"
EXTENSIONS_DIR="${HOME}/.openclaw/extensions"
PLUGIN_DIR="${EXTENSIONS_DIR}/${PLUGIN_ID}"
ENV_FILE="${HOME}/.openclaw/.env"

# 1. Clone or update the plugin into ~/.openclaw/extensions/otel-observability
mkdir -p "${EXTENSIONS_DIR}"
if [[ -d "${PLUGIN_DIR}/.git" ]]; then
  echo "Plugin already cloned at ${PLUGIN_DIR} — pulling latest."
  git -C "${PLUGIN_DIR}" pull --ff-only
else
  echo "Cloning ${PLUGIN_REPO} into ${PLUGIN_DIR}"
  git clone "${PLUGIN_REPO}" "${PLUGIN_DIR}"
fi

# 2. Install plugin dependencies
( cd "${PLUGIN_DIR}" && npm install --omit=dev )

# 3. Configure OpenClaw via the openclaw config CLI.
#    Settings persist to ~/.openclaw/openclaw.json.
openclaw config set diagnostics.enabled true
openclaw config set diagnostics.otel.enabled true
openclaw config set diagnostics.otel.traces true
openclaw config set diagnostics.otel.metrics true
openclaw config set diagnostics.otel.logs true
openclaw config set diagnostics.otel.protocol http/protobuf
openclaw config set diagnostics.otel.endpoint "${OTLP_ENDPOINT}"
openclaw config set diagnostics.otel.headers "{\"Authorization\":\"Api-Token ${DT_TOKEN}\"}"
openclaw config set diagnostics.otel.serviceName openclaw-gateway

# 4. Register the plugin entry. The entry id MUST be `otel-observability`
#    (matches the plugin manifest) — using the repo name will silently fail to load.
openclaw config set "plugins.load.paths" "[\"${PLUGIN_DIR}\"]"
openclaw config set "plugins.entries.otel-observability.enabled" true

# 5. Dynatrace requires delta temporality for OTLP metrics.
mkdir -p "$(dirname "${ENV_FILE}")"
if grep -q '^OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=' "${ENV_FILE}" 2>/dev/null; then
  sed -i 's|^OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=.*|OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta|' "${ENV_FILE}"
else
  printf 'OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta\n' >> "${ENV_FILE}"
fi

# 6. Clear the TS plugin loader cache and restart the gateway.
rm -rf /tmp/jiti
if systemctl --user is-enabled --quiet openclaw-gateway 2>/dev/null; then
  systemctl --user restart openclaw-gateway
  echo "OpenClaw gateway restarted."
else
  echo "Service openclaw-gateway not managed by systemd --user; restart manually."
fi

cat <<EOF

Setup complete.
  Plugin   : ${PLUGIN_DIR}
  Endpoint : ${OTLP_ENDPOINT}
  Env file : ${ENV_FILE}

Next steps:
  - Tail the gateway log for [otel] hook-registration lines:
      journalctl --user -u openclaw-gateway -f | grep -E '\\[otel\\]'
  - Send a real message through OpenClaw and verify a connected
    'openclaw.request' -> 'openclaw.agent.turn' -> 'tool.*' trace
    appears in Dynatrace under service.name = openclaw-gateway.
EOF
