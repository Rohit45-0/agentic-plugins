#!/bin/sh
set -eu

if [ -n "${GOOGLE_SERVICE_ACCOUNT_JSON:-}" ]; then
  printf "%s" "$GOOGLE_SERVICE_ACCOUNT_JSON" > /tmp/gsa.json
  export GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/tmp/gsa.json
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
