#!/usr/bin/env bash
#
# Deploys the app to App Engine, after the full CI gate passes.
#
# Usage:  ./tools/deploy.sh [extra `gcloud app deploy` flags, e.g. --no-promote]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT="one-holiday-calendar"

if ! command -v gcloud > /dev/null; then
  echo "gcloud not found: install the Google Cloud CLI first." >&2
  exit 1
fi

./tools/ci.sh
exec gcloud --project="$PROJECT" app deploy app.yaml "$@"
