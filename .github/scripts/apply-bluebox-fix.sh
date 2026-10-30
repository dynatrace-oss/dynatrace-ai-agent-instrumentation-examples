#!/usr/bin/env bash
# Extracts the first ```diff block from a comment body, stages it in the
# current checkout, and keeps it only if every staged change is to a file a
# dependency fix may touch. Used by the apply-fix workflow; it never runs code
# from the diff.
#
# Checks run on what git staged, not on the diff text, so path quoting,
# renames and header tricks can't hide a file.
#
# Inputs (environment variables):
#   COMMENT_FILE - file holding the comment body with the ```diff block
#   DIFF_FILE    - where to write the extracted diff (default: fix.diff)
set -euo pipefail

COMMENT_FILE="${COMMENT_FILE:?COMMENT_FILE is required}"
DIFF_FILE="${DIFF_FILE:-fix.diff}"

# Dependency manifests, the Renovate config (allowedVersions caps) and docs
# outside .github/. Everything else, including Makefiles, scripts and app
# code, runs in E2E next to its secrets and is fixed by hand.
ALLOWED='^(\.github/renovate\.json|(.*/)?(requirements[^/]*\.txt|pyproject\.toml|package\.json|go\.mod)|.*\.md)$'
DENIED='^\.github/(.*/)?[^/]*\.md$'

awk '/^```diff[[:space:]]*$/ && !done {f=1; next} f && /^```[[:space:]]*$/ {f=0; done=1} f' \
  "$COMMENT_FILE" > "$DIFF_FILE"

if [ ! -s "$DIFF_FILE" ]; then
  echo "::error::No \`\`\`diff block found in the fix comment."
  exit 1
fi

git apply --index "$DIFF_FILE"

# Mode changes, symlinks (mode 120000) and binaries are never part of a fix.
if git diff --cached --summary --no-renames | grep -qE 'mode (change|120000)'; then
  echo "::error::Diff changes file modes or adds a symlink."
  exit 1
fi
if git diff --cached --numstat --no-renames | grep -qE $'^-\t-\t'; then
  echo "::error::Diff contains binary changes."
  exit 1
fi

bad=()
while IFS= read -r -d '' path; do
  if ! [[ "$path" =~ $ALLOWED ]] || [[ "$path" =~ $DENIED ]]; then bad+=("$path"); fi
done < <(git diff --cached --name-only --no-renames -z)

if [ "${#bad[@]}" -gt 0 ]; then
  echo "::error::Diff touches files a triage fix may not change:"
  printf '%s\n' "${bad[@]}"
  exit 1
fi

git diff --cached --name-only --no-renames
