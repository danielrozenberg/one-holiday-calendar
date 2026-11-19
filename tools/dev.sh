#!/usr/bin/env bash
#
# Runs the app locally, restarting it whenever code or assets change.
#
# Usage:  ./tools/dev.sh [flask run options, e.g. --port 8080]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV_BIN="${ROOT}/.venv/bin"
if [[ -x "${VENV_BIN}/flask" ]]; then
  PATH="${VENV_BIN}:${PATH}"
fi

PACKAGE="src/one_holiday_calendar"
EXTRA_FILES="$(find "$PACKAGE" -type f ! -name '*.py' ! -path '*/__pycache__/*' \
  | paste -sd:)"

exec flask --app one_holiday_calendar.main run --debug --extra-files "$EXTRA_FILES" "$@"
