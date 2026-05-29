#!/usr/bin/env bash
# Sets up OpenPipeline routing so OpenInference spans are directed to the
# openinference-ai-spans pipeline.  Uses the Dynatrace Settings API v2.
#
# Requires both tokens in .env:
#   DT_PLATFORM_TOKEN=dt0s16.*  — Bearer auth, used to look up the dtctl-deployed pipeline objectId
#   DT_API_TOKEN=dt0c01.*       — Api-Token auth, used to read/write the system routing table
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-source .env if present (plain KEY=value format)
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a; source "$SCRIPT_DIR/.env"; set +a
fi

DT_ENDPOINT="${DT_ENDPOINT:?DT_ENDPOINT is required}"
DT_PLATFORM_TOKEN="${DT_PLATFORM_TOKEN:?DT_PLATFORM_TOKEN is required (dt0s16.* platform token)}"
DT_API_TOKEN="${DT_API_TOKEN:?DT_API_TOKEN is required (dt0c01.* classic token for routing table)}"

PIPELINE_CUSTOM_ID="openinference-ai-spans"
ROUTING_MATCHER='matchesPhrase(otel.scope.name, "openinference")'
ROUTING_DESC="Route OpenInference (Arize Phoenix) spans to openinference-ai-spans pipeline"

echo "→ Setting up routing for '$PIPELINE_CUSTOM_ID'..."

export PIPELINE_CUSTOM_ID ROUTING_MATCHER ROUTING_DESC

python3 << 'PYEOF'
import json, urllib.request, ssl, sys, os

endpoint = os.environ["DT_ENDPOINT"].rstrip("/")
platform_token = os.environ["DT_PLATFORM_TOKEN"]
api_token = os.environ["DT_API_TOKEN"]
pipeline_id = os.environ["PIPELINE_CUSTOM_ID"]
matcher = os.environ["ROUTING_MATCHER"]
desc = os.environ["ROUTING_DESC"]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api_get(path, token, bearer=False):
    auth = f"Bearer {token}" if bearer else f"Api-Token {token}"
    req = urllib.request.Request(f"{endpoint}{path}", headers={"Authorization": auth, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

def api_put(path, data, token, bearer=False):
    auth = f"Bearer {token}" if bearer else f"Api-Token {token}"
    req = urllib.request.Request(
        f"{endpoint}{path}", data=json.dumps(data).encode(),
        headers={"Authorization": auth, "Content-Type": "application/json"}, method="PUT"
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

# Look up pipeline objectId via platform token (dtctl-deployed pipelines are only visible with Bearer auth)
print("→ Fetching pipeline objectId (platform token)...")
pipelines = api_get("/api/v2/settings/objects?schemaIds=builtin:openpipeline.spans.pipelines", platform_token, bearer=True)
pipeline_obj_id = next(
    (i["objectId"] for i in pipelines.get("items", []) if i.get("value", {}).get("customId") == pipeline_id),
    None,
)
if not pipeline_obj_id:
    print(f"ERROR: pipeline '{pipeline_id}' not found — run dtctl apply first.", file=sys.stderr)
    sys.exit(1)
print(f"  objectId: {pipeline_obj_id}")

# Read/write system routing table via classic token (system-level routing, used by ingest)
print("→ Fetching routing settings (classic token)...")
routing = api_get("/api/v2/settings/objects?schemaIds=builtin:openpipeline.spans.routing", api_token)
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
api_put(f"/api/v2/settings/objects/{object_id}", {"value": value}, api_token)
print("✓ Routing entry added.")
PYEOF
