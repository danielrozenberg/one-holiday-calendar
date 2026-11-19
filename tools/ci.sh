#!/usr/bin/env bash
#
# Full local gate: format check, lint, type-check, tests, browser tests. Run
# before committing.
#
# It only checks the repo (writes only to temp dirs, uses only localhost), so it
# is safe to add to your Claude Code always-allow list as `Bash(./tools/ci.sh)`.
#
# Usage:  ./tools/ci.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# The project uses pyenv-virtualenv; the `.python-version` in the repo root
# auto-selects it, so ruff/pyrefly/pytest resolve via the pyenv shims. Fall back
# to a local .venv if one is present.
VENV_BIN="${ROOT}/.venv/bin"
if [[ -x "${VENV_BIN}/ruff" ]]; then
  PATH="${VENV_BIN}:${PATH}"
fi

run() {
  echo ":: $*"
  "$@"
}

run ruff format --check .
run ruff check .
run pyrefly check
echo ":: protobuf gencode freshness"
GEN="$(mktemp -d)"
trap 'rm -rf "$GEN"' EXIT
"$ROOT/tools/genproto.sh" "$GEN" > /dev/null
for f in "$GEN"/*; do
  diff -q "$f" "src/one_holiday_calendar/$(basename "$f")" \
    || { echo "Stale gencode: run ./tools/genproto.sh"; exit 1; }
done

run python -m pytest -q

# Browser tests start the app and a headless Chrome on free local ports.
if command -v node > /dev/null && command -v "${CHROME:-google-chrome}" > /dev/null; then
  run node tests/browser/run.mjs
else
  echo ":: skipping browser tests (needs node and google-chrome)"
fi

echo "OK: all gate checks passed."
