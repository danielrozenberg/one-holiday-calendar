#!/usr/bin/env bash
#
# Regenerates the protobuf Python code and type stubs from proto/.
#
# Usage:  ./tools/genproto.sh [OUT_DIR]   (default: src/one_holiday_calendar)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV_BIN="${ROOT}/.venv/bin"
if [[ -x "${VENV_BIN}/python" ]]; then
  PATH="${VENV_BIN}:${PATH}"
fi

OUT="${1:-src/one_holiday_calendar}"
python -m grpc_tools.protoc -I proto \
  --python_out="$OUT" --mypy_out="$OUT" proto/*.proto
