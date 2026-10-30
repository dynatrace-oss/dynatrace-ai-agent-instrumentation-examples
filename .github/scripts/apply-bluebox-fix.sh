#!/usr/bin/env bash
# Extracts the first ```diff block from a comment body and applies it to the
# current checkout, refusing any change outside the paths a dependency fix may
# touch. Used by the apply-fix workflow; it never runs code from the diff.
#
# Inputs (environment variables):
#   COMMENT_FILE - file holding the comment body with the ```diff block
#   DIFF_FILE    - where to write the extracted diff (default: fix.diff)
set -euo pipefail

COMMENT_FILE="${COMMENT_FILE:?COMMENT_FILE is required}"
DIFF_FILE="${DIFF_FILE:-fix.diff}"

awk '/^```diff[[:space:]]*$/ && !done {f=1; next} f && /^```[[:space:]]*$/ {f=0; done=1} f' \
  "$COMMENT_FILE" > "$DIFF_FILE"

if [ ! -s "$DIFF_FILE" ]; then
  echo "::error::No \`\`\`diff block found in the fix comment."
  exit 1
fi

# Binary patches, symlinks and mode changes are never part of a dependency fix.
if grep -qE '^(GIT binary patch|Binary files |(new |deleted )?file mode 120000|old mode |new mode )' "$DIFF_FILE"; then
  echo "::error::Diff contains binary, symlink or mode changes."
  exit 1
fi

# git C-quotes paths with spaces or non-ASCII bytes ("b/.github/\303\251.yml"),
# which would slip past the prefix checks below. No fix needs such a path.
if grep -qE '^(diff --git |--- |\+\+\+ |(rename|copy) (from|to) ).*"' "$DIFF_FILE"; then
  echo "::error::Diff contains quoted paths."
  exit 1
fi

# Every path the diff names, including both sides of renames and copies.
paths=$(
  {
    git apply --numstat "$DIFF_FILE" | cut -f3
    grep -E '^(rename|copy) (from|to) ' "$DIFF_FILE" | cut -d' ' -f3-
    grep -E '^(\+\+\+|---) [ab]/' "$DIFF_FILE" | cut -c7-
  } | sort -u
)

if unsafe=$(printf '%s\n' "$paths" | grep -vE '^[A-Za-z0-9._/@+-]+$'); then
  echo "::error::Diff names paths with unexpected characters:"
  printf '%s\n' "$unsafe"
  exit 1
fi

forbidden='^(\.github/|test/|\.git/)|(^|/)(package-lock\.json|uv\.lock|poetry\.lock|Pipfile\.lock|yarn\.lock|pnpm-lock\.yaml|go\.sum)$|(^|/)\.\.(/|$)'
if bad=$(printf '%s\n' "$paths" | grep -E "$forbidden"); then
  echo "::error::Diff touches paths a fix may not change:"
  printf '%s\n' "$bad"
  exit 1
fi

git apply --check "$DIFF_FILE"
git apply "$DIFF_FILE"
printf '%s\n' "$paths"
