#!/usr/bin/env bash
# Structural + unit test gate for m2map.
#
# Runs from the repo root, in CI and locally:
#   bash tests/run-all.sh
#
# Exits non-zero on the first failing check so a broken skill never propagates
# to the generated Codex / Cursor / Cline / Windsurf / Copilot variants.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

fail=0
pass=0

run() {
  local name="$1"
  shift
  printf '%-44s' "$name"
  if output=$("$@" 2>&1); then
    printf 'PASS\n'
    pass=$((pass + 1))
  else
    printf 'FAIL\n'
    printf '%s\n' "$output" | sed 's/^/    /'
    fail=$((fail + 1))
  fi
}

exists() {
  [ -e "$1" ] || { echo "missing: $1"; return 1; }
}

# --- structural: the files every mode depends on --------------------------

run "skill entry point"        exists skills/m2map/SKILL.md
run "mental model (floor doc)" exists skills/m2map/reference/mental-model.md
run "format spec vendored"     exists skills/m2map/reference/mapformat/README.md
run "activation rule source"   exists rules/m2map-activate.md
run "claude plugin manifest"   exists .claude-plugin/plugin.json
run "codex plugin manifest"    exists plugins/m2map/.codex-plugin/plugin.json

# --- generated variants are in step with the source of truth --------------

run "agent variants synced"    python tools/sync.py --check

# --- python unit tests ----------------------------------------------------

if command -v python >/dev/null 2>&1; then
  if python -c "import pytest" >/dev/null 2>&1; then
    run "pytest" python -m pytest tests -q
  else
    printf '%-44s%s\n' "pytest" "SKIP (pytest not installed)"
  fi
fi

echo
echo "passed: $pass   failed: $fail"
[ "$fail" -eq 0 ]
