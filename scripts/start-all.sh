#!/usr/bin/env bash
#
# start-all.sh — boot the full local Jobify stack in the background.
#
# Brings up (idempotently — safe to re-run):
#   • Postgres 16  (Homebrew service)        • Celery worker (parse/embed/score/notify)
#   • Redis        (Homebrew service)         • Frontend     (Vite dev server  :5173)
#   • Alembic migrations → head               • Flutter web  (:8080, opt-in)
#   • API          (FastAPI/uvicorn  :8000)
#
# Logs + PID files land in var/run/ (gitignored). Stop everything with
# scripts/stop-all.sh.
#
# Usage:  scripts/start-all.sh [--with-flutter]
#   --with-flutter   also launch the Flutter web client on :8080 (slow DDC build)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/var/run"
ENV_FILE="$ROOT/.env"

WITH_FLUTTER=0
for arg in "$@"; do
  case "$arg" in
    --with-flutter) WITH_FLUTTER=1 ;;
    -h|--help) sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'start-all: unknown arg: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;34m▸\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[31m✗ start-all: %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "no .env at repo root ($ENV_FILE). Copy .env.example → .env first."
mkdir -p "$RUN_DIR"

port_up()  { lsof -i ":$1" -sTCP:LISTEN -t >/dev/null 2>&1; }
running()  { local f=$1; [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; }

# ensure_brew <service> — start a Homebrew service unless already started.
ensure_brew() {
  local svc=$1
  if brew services list 2>/dev/null | grep -qE "^$svc[[:space:]]+started"; then
    ok "$svc already running"
  else
    say "starting $svc (Homebrew)…"
    brew services start "$svc" >/dev/null && ok "$svc started"
  fi
}

# spawn <name> <pidfile> <logfile> <command-string>
# Runs the command via `nohup bash -c`; the command must end in `exec <real>`
# so the recorded PID is the real process (its child tree is killed on stop).
spawn() {
  local name=$1 pidfile=$2 logfile=$3 cmd=$4
  if running "$pidfile"; then
    warn "$name already running (pid $(cat "$pidfile")) — skipping"
    return 0
  fi
  nohup bash -c "$cmd" >"$logfile" 2>&1 &
  local pid=$!
  echo "$pid" >"$pidfile"
  ok "$name started (pid $pid) → ${logfile#$ROOT/}"
}

# ── 1. Shared infra ────────────────────────────────────────────────────────
say "Ensuring Postgres + Redis are up…"
ensure_brew postgresql@16
ensure_brew redis

# ── 2. Migrations (canary: catches drift before the API serves 500s) ───────
say "Applying Alembic migrations (→ head)…"
( cd "$ROOT/core" && uv run --env-file="$ENV_FILE" alembic upgrade head >/dev/null 2>&1 ) \
  && ok "DB at head" || die "alembic upgrade failed — run: cd core && uv run --env-file=../.env alembic upgrade head"

# ── 3. App-layer services ──────────────────────────────────────────────────
say "Starting API, worker, frontend…"
spawn api "$RUN_DIR/api.pid" "$RUN_DIR/api.log" \
  "cd '$ROOT' && exec uv run --env-file='$ENV_FILE' uvicorn jobify_api.main:app --reload --port 8000"

spawn worker "$RUN_DIR/worker.pid" "$RUN_DIR/worker.log" \
  "cd '$ROOT' && exec uv run --env-file='$ENV_FILE' celery -A jobify_worker.worker_app worker --pool=solo --concurrency=1 -Q parse,embed,score,notify --loglevel=info"

spawn frontend "$RUN_DIR/frontend.pid" "$RUN_DIR/frontend.log" \
  "cd '$ROOT/frontend' && exec npm run dev"

if [ "$WITH_FLUTTER" -eq 1 ]; then
  spawn flutter "$RUN_DIR/flutter.pid" "$RUN_DIR/flutter.log" \
    "cd '$ROOT/app' && exec flutter run -d web-server --web-port=8080 --dart-define-from-file=.env"
fi

# ── 4. Wait for the API to answer (the readiness gate) ─────────────────────
say "Waiting for API /health…"
for _ in $(seq 1 20); do
  curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  sleep 1
done
if curl -sf http://127.0.0.1:8000/ready >/dev/null 2>&1; then
  ok "API ready (db ok)"
else
  warn "API not ready yet — check var/run/api.log"
fi

# ── 5. Summary ─────────────────────────────────────────────────────────────
printf '\n\033[1mServices\033[0m\n'
printf '  API        http://127.0.0.1:8000   (/docs, /health, /ready)\n'
printf '  Frontend   http://localhost:5173   (/, /#/employers, /#/console)\n'
[ "$WITH_FLUTTER" -eq 1 ] && printf '  Flutter    http://localhost:8080   (DDC build — first paint is slow)\n'
printf '  Worker     queues: parse, embed, score, notify\n'
printf '\nLogs: %s/*.log   ·   Stop: scripts/stop-all.sh%s\n' \
  "${RUN_DIR#$ROOT/}" "$([ "$WITH_FLUTTER" -eq 1 ] && echo '' )"
