#!/bin/bash
# Setup script for OpenAI Codex CLI OTEL telemetry with Dynatrace
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

# Normalise: strip trailing signal-specific path segments
for _suffix in "/v1/traces" "/v1/metrics" "/v1/logs"; do
  if [[ "$DT_OTEL_ENDPOINT" == *"$_suffix" ]]; then
    DT_OTEL_ENDPOINT="${DT_OTEL_ENDPOINT%$_suffix}"
  fi
done

# Resolve Codex home (~/.codex by default, or $CODEX_HOME if set)
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_CONFIG_FILE="$CODEX_HOME/config.toml"

mkdir -p "$CODEX_HOME"

# Merge the [otel] block into ~/.codex/config.toml using Python
if command -v python3 &>/dev/null; then
  python3 - <<PYEOF
import sys

try:
    import tomllib
    import tomli_w
    has_toml_libs = True
except ImportError:
    has_toml_libs = False

import os, re

config_file = "$CODEX_CONFIG_FILE"
endpoint    = "$DT_OTEL_ENDPOINT"
token       = "$DT_API_TOKEN"

otel_block = f"""
[otel]
environment = "prod"
log_user_prompt = false

[otel.exporter.otlp-http]
endpoint = "{endpoint}/v1/logs"
protocol = "binary"

[otel.exporter.otlp-http.headers]
Authorization = "Api-Token {token}"

[otel.trace_exporter.otlp-http]
endpoint = "{endpoint}/v1/traces"
protocol = "binary"

[otel.trace_exporter.otlp-http.headers]
Authorization = "Api-Token {token}"
"""

# Read existing config, strip any previous [otel*] sections, append new block
existing = ""
if os.path.exists(config_file):
    with open(config_file) as f:
        existing = f.read()

# Remove existing [otel] sections by splitting on top-level headers and filtering
parts = re.split(r'(?=^\[)', existing, flags=re.MULTILINE)
cleaned = ''.join(p for p in parts if not re.match(r'\[otel', p.lstrip())).rstrip()

with open(config_file, "w") as f:
    if cleaned:
        f.write(cleaned + "\n")
    f.write(otel_block)

print(f"  Written: {config_file}")
PYEOF
else
  echo "ERROR: python3 is required to update config.toml"
  return 1 2>/dev/null || exit 1
fi

echo "OpenAI Codex CLI telemetry configured for Dynatrace:"
echo "  Endpoint : $DT_OTEL_ENDPOINT"
echo "  Config   : $CODEX_CONFIG_FILE"
echo ""
echo "Run 'codex' to start a session with telemetry enabled."
