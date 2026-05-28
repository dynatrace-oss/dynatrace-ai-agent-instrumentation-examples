#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# deploy-openpipeline.sh
#
# Deploys the OpenInference AI observability OpenPipeline span config to a
# Dynatrace tenant via the Settings API v2, then sets up the routing entry.
#
# Prerequisites:
#   - DT_ENDPOINT: your tenant URL (e.g. https://<id>.live.dynatrace.com)
#   - DT_API_TOKEN: API token with settings:read and settings:write scopes
#   - python3 with pyyaml: pip install pyyaml
#
# Usage:
#   export DT_ENDPOINT=https://<id>.live.dynatrace.com
#   export DT_API_TOKEN=dt0c01.***
#   ./deploy-openpipeline.sh
#   ./deploy-openpipeline.sh --dry-run   # validate only, no writes
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_YAML="$SCRIPT_DIR/openpipeline-openinference.yaml"

if [[ -z "${DT_ENDPOINT:-}" || -z "${DT_API_TOKEN:-}" ]]; then
  echo "ERROR: DT_ENDPOINT and DT_API_TOKEN must be set" >&2
  exit 1
fi

if ! python3 -c "import yaml" 2>/dev/null; then
  echo "ERROR: python3 module 'pyyaml' is required. Install with: pip install pyyaml" >&2
  exit 1
fi

ENV_URL="${DT_ENDPOINT%/}"
# Strip .apps. subdomain — Settings API lives on the base domain
ENV_URL="${ENV_URL/.apps./.}"

echo "Environment: $ENV_URL"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "*** DRY-RUN MODE — validate only, no writes ***"
fi
echo ""

# --- Convert openpipeline YAML → Settings API JSON --------------------------
api_json=$(python3 - "$PIPELINE_YAML" <<'PYEOF'
import yaml, json, sys

with open(sys.argv[1]) as f:
    doc = yaml.safe_load(f)

processors = []
for p in doc.get("processing", {}).get("processors", []):
    proc = {
        "id": p["id"],
        "type": p["type"],
        "matcher": p["matcher"],
        "description": p.get("description", ""),
        "enabled": p.get("enabled", True),
        "sampleData": None,
    }
    if p["type"] == "fieldsAdd":
        proc["fieldsAdd"] = {
            "fields": [{"name": f["name"], "value": f["value"]} for f in p["fieldsAdd"]["fields"]]
        }
    elif p["type"] == "fieldsRename":
        proc["fieldsRename"] = {
            "fields": [{"fromName": f["fromName"], "toName": f["toName"]} for f in p["fieldsRename"]["fields"]]
        }
    elif p["type"] == "fieldsRemove":
        proc["fieldsRemove"] = {"fields": p["fieldsRemove"]["fields"]}
    elif p["type"] == "dql":
        proc["dql"] = {"script": p["dql"]["script"].strip()}
    else:
        print(f"WARNING: Unknown processor type: {p['type']}", file=sys.stderr)
    processors.append(proc)

payload = [{
    "schemaId": "builtin:openpipeline.spans.pipelines",
    "scope": "environment",
    "value": {
        "customId": doc["customId"],
        "displayName": doc["displayName"],
        "metadataList": [],
        "routing": "routable",
        "processing": {"processors": processors},
    },
}]
json.dump(payload, sys.stdout)
PYEOF
)

custom_id=$(echo "$api_json" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['value']['customId'])")
proc_count=$(echo "$api_json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)[0]['value']['processing']['processors']))")
HEADERS=(-H "Authorization: Api-Token $DT_API_TOKEN" -H "Content-Type: application/json; charset=utf-8")

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Pipeline: $custom_id ($proc_count processors)"
echo ""

# --- Validate ----------------------------------------------------------------
echo -n "Validating... "
val_resp=$(curl -s -X POST \
  "$ENV_URL/api/v2/settings/objects?validateOnly=true" \
  "${HEADERS[@]}" -d "$api_json")

python3 -c "
import json, sys
data = json.loads(sys.argv[1])
if isinstance(data, dict) and 'error' in data:
    print(f\"FAILED: {data['error'].get('message', data['error'])}\")
    sys.exit(1)
errors = [i for i in (data if isinstance(data, list) else []) if i.get('code', 0) >= 400]
if errors:
    print('FAILED:', errors)
    sys.exit(1)
print('OK')
" "$val_resp" || { echo "Response: $val_resp"; exit 1; }

$DRY_RUN && { echo "Dry-run complete."; exit 0; }

# --- Check if pipeline exists ------------------------------------------------
existing_oid=$(curl -sf \
  "$ENV_URL/api/v2/settings/objects?schemaIds=builtin:openpipeline.spans.pipelines&fields=objectId,value" \
  -H "Authorization: Api-Token $DT_API_TOKEN" \
  -H "Accept: application/json" \
| python3 -c "
import json, sys
for item in json.load(sys.stdin).get('items', []):
    if item.get('value', {}).get('customId') == '$custom_id':
        print(item['objectId']); sys.exit(0)
sys.exit(1)
" 2>/dev/null || echo "")

if [[ -n "$existing_oid" ]]; then
  echo "Updating existing pipeline ($existing_oid)..."
  existing_value=$(curl -sf \
    "$ENV_URL/api/v2/settings/objects/$existing_oid" \
    -H "Authorization: Api-Token $DT_API_TOKEN" -H "Accept: application/json" \
  | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['value']))")

  update_body=$(python3 -c "
import json, sys
existing = json.loads(sys.argv[1])
new = json.loads(sys.argv[2])[0]['value']
existing['displayName'] = new['displayName']
existing['processing'] = new['processing']
print(json.dumps(existing))
" "$existing_value" "$api_json")

  resp=$(curl -s -X PUT \
    "$ENV_URL/api/v2/settings/objects/$existing_oid" \
    "${HEADERS[@]}" -d "{\"value\": $update_body}")
  echo "Update response: $resp"
else
  echo "Creating new pipeline..."
  resp=$(curl -s -X POST \
    "$ENV_URL/api/v2/settings/objects" \
    "${HEADERS[@]}" -d "$api_json")
  echo "Create response: $resp"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Setting up routing..."
echo ""

# --- Routing setup -----------------------------------------------------------
python3 - <<PYEOF
import json, requests, sys

base = "$ENV_URL"
headers = {"Authorization": "Api-Token $DT_API_TOKEN", "Content-Type": "application/json"}

# Resolve pipeline object ID by customId
r = requests.get(
    f"{base}/api/v2/settings/objects",
    params={"schemaIds": "builtin:openpipeline.spans.pipelines", "scopes": "environment", "pageSize": 500},
    headers=headers
)
pipeline_id = None
for p in r.json().get("items", []):
    if p["value"].get("customId") == "openinference-ai-spans":
        pipeline_id = p["objectId"]
        break

if not pipeline_id:
    print("ERROR: pipeline 'openinference-ai-spans' not found — did deployment succeed?")
    sys.exit(1)

print(f"  Pipeline objectId: {pipeline_id[:40]}...")

new_entry = {
    "enabled": True,
    "pipelineType": "custom",
    "pipelineId": pipeline_id,
    "matcher": 'matchesPhrase(otel.scope.name, "openinference")',
    "description": "Route OpenInference (Arize Phoenix) spans to openinference-ai-spans pipeline"
}

# Get existing routing config
r = requests.get(
    f"{base}/api/v2/settings/objects",
    params={"schemaIds": "builtin:openpipeline.spans.routing", "scopes": "environment", "pageSize": 500},
    headers=headers
)
items = r.json().get("items", [])

if items:
    obj_id = items[0]["objectId"]
    existing = items[0]["value"]
    existing_entries = existing.get("routingEntries", [])
    kept = [e for e in existing_entries if e.get("description") != new_entry["description"]]
    existing["routingEntries"] = kept + [new_entry]
    r2 = requests.put(
        f"{base}/api/v2/settings/objects/{obj_id}",
        headers=headers, json={"value": existing}
    )
    print(f"  Updated routing: {r2.status_code}")
    if r2.status_code != 200:
        print(r2.text)
else:
    payload = [{"schemaId": "builtin:openpipeline.spans.routing", "scope": "environment",
                "value": {"routingEntries": [new_entry]}}]
    r2 = requests.post(f"{base}/api/v2/settings/objects", headers=headers, json=payload)
    print(f"  Created routing: {r2.status_code}")
    if r2.status_code not in (200, 201):
        print(r2.text)

print("")
print("Done.")
PYEOF
