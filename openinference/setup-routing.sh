#!/usr/bin/env bash
# Sets up OpenPipeline routing so OpenInference spans are directed to the
# openinference-ai-spans pipeline.  Requires dtctl to be configured with a
# valid context (run `dtctl ctx set ...` first).
set -euo pipefail

PIPELINE_CUSTOM_ID="openinference-ai-spans"
ROUTING_MATCHER='matchesPhrase(otel.scope.name, "openinference")'
ROUTING_DESC="Route OpenInference (Arize Phoenix) spans to openinference-ai-spans pipeline"

echo "→ Fetching pipeline objectId for '$PIPELINE_CUSTOM_ID'..."
PIPELINE_ID=$(dtctl get settings --schema builtin:openpipeline.spans.pipelines -o json \
  | python3 -c "
import json, sys
items = json.load(sys.stdin)
match = next((i['objectId'] for i in items if i.get('value', {}).get('customId') == '$PIPELINE_CUSTOM_ID'), None)
if not match:
    print('ERROR: pipeline not found', file=sys.stderr); sys.exit(1)
print(match)
")
echo "  objectId: $PIPELINE_ID"

TMP=$(mktemp /tmp/routing.XXXXXX.yaml)
trap "rm -f $TMP" EXIT

echo "→ Fetching current routing config..."
dtctl get settings --schema builtin:openpipeline.spans.routing --scope environment -o yaml > "$TMP"

echo "→ Adding routing entry..."
python3 - "$TMP" "$PIPELINE_ID" "$ROUTING_MATCHER" "$ROUTING_DESC" << 'PYEOF'
import yaml, sys
with open(sys.argv[1]) as f:
    routing = yaml.safe_load(f)
new_entry = {
    "enabled": True,
    "pipelineType": "custom",
    "pipelineId": sys.argv[2],
    "matcher": sys.argv[3],
    "description": sys.argv[4],
}
for obj in routing:
    entries = obj.get("value", {}).get("routingEntries", [])
    obj["value"]["routingEntries"] = (
        [e for e in entries if e.get("description") != new_entry["description"]]
        + [new_entry]
    )
with open(sys.argv[1], "w") as f:
    yaml.dump(routing, f, default_flow_style=False, allow_unicode=True)
PYEOF

echo "→ Applying routing config..."
dtctl apply -f "$TMP"
echo "✓ Routing entry set."
