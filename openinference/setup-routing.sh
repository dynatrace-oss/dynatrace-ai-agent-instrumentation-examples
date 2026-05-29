#!/usr/bin/env bash
# Sets up OpenPipeline routing so OpenInference spans are directed to the
# openinference-ai-spans pipeline.  Uses the Dynatrace Settings API v2
# with a platform token (dt0s16.*) — required when pipeline is deployed via dtctl.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-source .env if present (plain KEY=value format)
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a; source "$SCRIPT_DIR/.env"; set +a
fi

DT_ENDPOINT="${DT_ENDPOINT:?DT_ENDPOINT is required}"
DT_PLATFORM_TOKEN="${DT_PLATFORM_TOKEN:?DT_PLATFORM_TOKEN is required (platform token dt0s16.*)}"

PIPELINE_CUSTOM_ID="openinference-ai-spans"
ROUTING_MATCHER='matchesPhrase(otel.scope.name, "openinference")'
ROUTING_DESC="Route OpenInference (Arize Phoenix) spans to openinference-ai-spans pipeline"

echo "→ Setting up routing for '$PIPELINE_CUSTOM_ID'..."

export PIPELINE_CUSTOM_ID ROUTING_MATCHER ROUTING_DESC

python3 << 'PYEOF'
import json, urllib.request, ssl, sys, os

endpoint = os.environ["DT_ENDPOINT"].rstrip("/")
token = os.environ["DT_PLATFORM_TOKEN"]
pipeline_id = os.environ["PIPELINE_CUSTOM_ID"]
matcher = os.environ["ROUTING_MATCHER"]
desc = os.environ["ROUTING_DESC"]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def api_get(path):
    req = urllib.request.Request(f"{endpoint}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

def api_put(path, data):
    req = urllib.request.Request(
        f"{endpoint}{path}", data=json.dumps(data).encode(), headers=headers, method="PUT"
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

# Resolve pipeline objectId from its customId
print("→ Fetching pipeline objectId...")
pipelines = api_get("/api/v2/settings/objects?schemaIds=builtin:openpipeline.spans.pipelines")
pipeline_obj_id = next(
    (i["objectId"] for i in pipelines.get("items", []) if i.get("value", {}).get("customId") == pipeline_id),
    None,
)
if not pipeline_obj_id:
    print(f"ERROR: pipeline '{pipeline_id}' not found — run dtctl apply first.", file=sys.stderr)
    sys.exit(1)
print(f"  objectId: {pipeline_obj_id}")

# Fetch routing settings object
print("→ Fetching routing settings...")
routing = api_get("/api/v2/settings/objects?schemaIds=builtin:openpipeline.spans.routing")
if not routing.get("items"):
    print("ERROR: No routing settings found.", file=sys.stderr)
    sys.exit(1)

item = routing["items"][0]
object_id = item["objectId"]
value = item["value"]

# Add routing entry (replace existing one with same description to avoid duplicates)
entries = value.get("routingEntries", [])
entries = [e for e in entries if e.get("description") != desc]
entries.append({
    "enabled": True,
    "pipelineType": "custom",
    "pipelineId": pipeline_obj_id,
    "matcher": matcher,
    "description": desc,
})
value["routingEntries"] = entries

print(f"→ Updating routing (objectId: {object_id})...")
api_put(f"/api/v2/settings/objects/{object_id}", {"value": value})
print("✓ Routing entry added.")
PYEOF
