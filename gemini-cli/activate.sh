#!/usr/bin/env bash
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Source this file (do NOT execute it) to export Gemini CLI telemetry env vars:
#   source activate.sh

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

# ── Gemini CLI telemetry toggle ───────────────────────────────────────────────
export GEMINI_TELEMETRY_ENABLED=true

# ── Target: custom OTLP endpoint (not GCP) ───────────────────────────────────
export GEMINI_TELEMETRY_TARGET=local

export GEMINI_TELEMETRY_OTLP_PROTOCOL=http

# ── Dynatrace OTLP ingress endpoint ──────────────────────────────────────────
export GEMINI_TELEMETRY_OTLP_ENDPOINT="${DT_OTEL_ENDPOINT}"

# ── Dynatrace authentication header ──────────────────────────────────────────
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token ${DT_API_TOKEN}"

# ── Dynatrace requires delta temporality for metrics ─────────────────────────
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta

# ── Prompt logging — Gemini CLI defaults to true; set false to suppress ───────
# Uncomment the second line to include prompts in log events.
export GEMINI_TELEMETRY_LOG_PROMPTS=false
# export GEMINI_TELEMETRY_LOG_PROMPTS=true

echo "✓  Gemini CLI → Dynatrace telemetry configured"
echo "   Endpoint : ${GEMINI_TELEMETRY_OTLP_ENDPOINT}"
echo "   Protocol : http/protobuf"
echo "   Auth     : OTEL_EXPORTER_OTLP_HEADERS set"
echo "   Delta    : OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta"
echo ""
echo "Run 'gemini' to start a session with telemetry enabled."
