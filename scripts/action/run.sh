#!/usr/bin/env bash
# Scan for changed screenshots; write causes to a file, the job summary and step outputs.
# Env: MODULE_DIR, SOURCE, BASE_REF (may be empty), RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_STEP_SUMMARY
set -uo pipefail
export PYTHONIOENCODING=utf-8   # the report has non-ASCII marks; Windows runners default to a code page
causes="$RUNNER_TEMP/diffsay-causes.md"
[ -d "$MODULE_DIR" ] || { echo "::error::diffsay: module-dir $MODULE_DIR not found"; exit 2; }
args=(scan "$MODULE_DIR" --source "${SOURCE:-$MODULE_DIR}" --markdown)

if [ -n "${BASE_REF:-}" ]; then
  # fetch only when missing: fetching with --depth into a full clone would make it shallow
  if git rev-parse --verify --quiet "origin/$BASE_REF" >/dev/null 2>&1 \
     || { git fetch --no-tags --depth=200 origin "$BASE_REF" >/dev/null 2>&1 \
          && git rev-parse --verify --quiet "origin/$BASE_REF" >/dev/null; }; then
    args+=(--diff "origin/$BASE_REF")
  else
    echo "::warning::diffsay: base ref unavailable, running without --diff"
  fi
fi

diffsay "${args[@]}" > "$causes"
status=$?
case $status in
  0) changed=false ;;
  1) changed=true
     # exit 1 is also Python's code for an uncaught exception: only a report counts as a change
     grep -q '^### ' "$causes" || { echo "::error::diffsay scan crashed (see the log above)"; exit 1; } ;;
  *) echo "::error::diffsay scan failed with exit $status"; exit "$status" ;;
esac

if [ "$changed" = true ]; then cat "$causes" >> "$GITHUB_STEP_SUMMARY"; else
  echo "No screenshot changes." >> "$GITHUB_STEP_SUMMARY"; fi
{ echo "changed=$changed"; echo "causes-file=$causes"; } >> "$GITHUB_OUTPUT"
