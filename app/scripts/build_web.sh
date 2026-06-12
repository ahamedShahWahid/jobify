#!/usr/bin/env bash
# Substitutes the GIS client id into web/index.template.html, writes
# web/index.html (gitignored), then runs `flutter build web`.
# Pass extra args after the script name; they're forwarded to
# `flutter build web`.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${JOBIFY_GOOGLE_WEB_CLIENT_ID:-}" ]]; then
  echo "JOBIFY_GOOGLE_WEB_CLIENT_ID is not set." >&2
  echo "Source your .env first or export it before running." >&2
  exit 1
fi

sed "s|{{GOOGLE_WEB_CLIENT_ID}}|${JOBIFY_GOOGLE_WEB_CLIENT_ID}|g" \
  web/index.template.html > web/index.html

flutter build web "$@"
