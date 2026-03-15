#!/bin/sh
set -eu

QUEUE="${1:-${WORKER_QUEUE:-}}"

if [ -z "$QUEUE" ]; then
  echo "Missing worker queue. Pass webhook_ingest, llm_reply, or media." >&2
  exit 1
fi

case "$QUEUE" in
  webhook_ingest|llm_reply|media)
    ;;
  *)
    echo "Unsupported worker queue: $QUEUE" >&2
    exit 1
    ;;
esac

if [ -n "${GOOGLE_SERVICE_ACCOUNT_JSON:-}" ]; then
  printf "%s" "$GOOGLE_SERVICE_ACCOUNT_JSON" > /tmp/gsa.json
  export GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/tmp/gsa.json
fi

exec celery -A app.worker.celery_app worker \
  --loglevel="${CELERY_LOGLEVEL:-info}" \
  --concurrency="${CELERY_CONCURRENCY:-2}" \
  -P solo \
  -Q "$QUEUE"
