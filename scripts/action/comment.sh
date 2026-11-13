#!/usr/bin/env bash
# Keep one diffsay comment per PR, found by its marker. Never fails the job.
# Env: REPO, PR, CHANGED, CAUSES_FILE, GH_TOKEN
set -uo pipefail
marker='<!-- diffsay -->'
body="$PWD/body.md"
warn() { echo "::warning::diffsay: could not comment (fork PR or missing pull-requests: write); see the job summary"; exit 0; }

if [ "$CHANGED" = true ]; then { echo "$marker"; cat "$CAUSES_FILE"; } > "$body"
else printf '%s\nNo screenshot changes in the latest push.\n' "$marker" > "$body"; fi

existing=$(gh api "repos/$REPO/issues/$PR/comments" --paginate \
  --jq ".[] | select(.body | startswith(\"$marker\")) | .id" | head -1) || warn

if [ -n "$existing" ]; then
  gh api --method PATCH "repos/$REPO/issues/comments/$existing" -F "body=@$body" >/dev/null || warn
elif [ "$CHANGED" = true ]; then
  gh pr comment "$PR" --repo "$REPO" --body-file "$body" >/dev/null || warn
fi
