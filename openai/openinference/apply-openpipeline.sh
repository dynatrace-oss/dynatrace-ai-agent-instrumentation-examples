#!/usr/bin/env bash
# Applies openpipeline-openinference.yaml to the current dtctl tenant as a
# builtin:openpipeline.spans.pipelines settings object.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_FILE="$SCRIPT_DIR/openpipeline-openinference.yaml"

if ! command -v dtctl &>/dev/null; then
  echo "ERROR: dtctl not found in PATH" >&2
  exit 1
fi

if ! command -v yq &>/dev/null; then
  echo "ERROR: yq not found in PATH (brew install yq)" >&2
  exit 1
fi

CONTEXT=$(dtctl config current-context 2>/dev/null)
TENANT=$(dtctl config describe-context "$CONTEXT" --plain 2>/dev/null | grep '^Environment:' | awk '{print $2}')

echo "Context : $CONTEXT"
echo "Tenant  : $TENANT"
echo "File    : $PIPELINE_FILE"
echo ""

# Wrap the pipeline definition in a dtctl settings envelope and apply via temp file
TMPFILE=$(mktemp /tmp/openpipeline-apply-XXXXXX.yaml)
trap 'rm -f "$TMPFILE"' EXIT

yq eval '. as $pipeline | {
  "schemaId": "builtin:openpipeline.spans.pipelines",
  "scope": "environment",
  "value": $pipeline
}' "$PIPELINE_FILE" > "$TMPFILE"

dtctl apply -f "$TMPFILE" "$@"
