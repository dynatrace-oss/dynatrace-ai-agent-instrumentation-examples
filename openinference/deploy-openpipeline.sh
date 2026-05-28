#!/usr/bin/env bash
# Deploys the OpenInference OpenPipeline configuration to Dynatrace
# using the Settings API v2 and a classic dt0c01.* API token.
# Usage: bash deploy-openpipeline.sh [--dry-run]
set -euo pipefail

DT_ENDPOINT="${DT_ENDPOINT:?DT_ENDPOINT is required (source .env first)}"
DT_API_TOKEN="${DT_API_TOKEN:?DT_API_TOKEN is required (source .env first)}"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DTCTL_YAML="$SCRIPT_DIR/openpipeline-openinference-dtctl.yaml"

python3 -c "import yaml" 2>/dev/null || { echo "Installing pyyaml..."; pip3 install pyyaml -q; }

if $DRY_RUN; then
  echo "Dry run — Settings API payload:"
  python3 - "$DTCTL_YAML" << 'PYEOF'
import yaml, json, sys
with open(sys.argv[1]) as f:
    docs = list(yaml.safe_load_all(f))
payload = [{"schemaId": d["schemaId"], "scope": d.get("scope", "environment"), "value": d["value"]} for d in docs]
print(json.dumps(payload, indent=2))
PYEOF
  exit 0
fi

echo "→ Deploying OpenPipeline configuration..."
python3 - "$DTCTL_YAML" << PYEOF
import yaml, json, urllib.request, sys, os

endpoint = os.environ["DT_ENDPOINT"].rstrip("/")
token = os.environ["DT_API_TOKEN"]

with open(sys.argv[1]) as f:
    docs = list(yaml.safe_load_all(f))

payload = [{"schemaId": d["schemaId"], "scope": d.get("scope", "environment"), "value": d["value"]} for d in docs]
data = json.dumps(payload).encode()

req = urllib.request.Request(
    f"{endpoint}/api/v2/settings/objects",
    data=data,
    headers={"Authorization": f"Api-Token {token}", "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
        print(json.dumps(body, indent=2))
        print("✓ Pipeline deployed successfully.")
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
PYEOF
