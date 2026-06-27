#!/usr/bin/env bash
#
# stop-all.sh — stop the local Jobify app-layer stack started by start-all.sh.
#
# Kills the FULL process tree of each service: `uvicorn --reload` forks a
# reloader child that respawns the server if you kill only the leaf, and the
# Celery worker has no listening port to target — so a naive `kill <pid>` or
# port-only kill leaves zombies. We recurse children-first, then sweep ports +
# the worker pattern as a safety net.
#
# Postgres + Redis (shared Homebrew infra) are LEFT RUNNING by default; pass
# --with-infra to stop them too.
#
# Usage:  scripts/stop-all.sh [--with-infra]
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/var/run"

WITH_INFRA=0
for arg in "$@"; do
  case "$arg" in
    --with-infra) WITH_INFRA=1 ;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'stop-all: unknown arg: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;34m▸\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
info() { printf '  \033[2m·\033[0m %s\n' "$*"; }

# kill_tree <pid> <signal> — kill all descendants first, then the pid itself.
kill_tree() {
  local pid=$1 sig=${2:-TERM} kid
  kill -0 "$pid" 2>/dev/null || return 0
  for kid in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$kid" "$sig"
  done
  kill -"$sig" "$pid" 2>/dev/null || true
}

# stop_pidfile <name> <pidfile>
stop_pidfile() {
  local name=$1 pidfile=$2 pid
  [ -f "$pidfile" ] || { info "$name: no pidfile"; return 0; }
  pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    kill_tree "$pid" TERM
    for _ in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -0 "$pid" 2>/dev/null && kill_tree "$pid" KILL
    ok "$name stopped (was pid $pid)"
  else
    info "$name already down"
  fi
  rm -f "$pidfile"
}

say "Stopping app-layer services…"
stop_pidfile flutter  "$RUN_DIR/flutter.pid"
stop_pidfile frontend "$RUN_DIR/frontend.pid"
stop_pidfile worker   "$RUN_DIR/worker.pid"
stop_pidfile api      "$RUN_DIR/api.pid"

# Safety net — catch anything respawned/orphaned that the pidfiles missed.
say "Sweeping ports + worker pattern…"
for port in 8000 5173 8080; do
  for p in $(lsof -ti ":$port" -sTCP:LISTEN 2>/dev/null || true); do
    kill_tree "$p" TERM
  done
done
for p in $(pgrep -f 'celery -A jobify_worker' 2>/dev/null || true); do
  kill_tree "$p" TERM
done
sleep 2

# Verify nothing is still listening.
leftover=0
for port in 8000 5173 8080; do
  if lsof -i ":$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    printf '  \033[33m!\033[0m :%s still up\n' "$port"; leftover=1
  fi
done
pgrep -f 'celery -A jobify_worker' >/dev/null 2>&1 && { printf '  \033[33m!\033[0m worker still up\n'; leftover=1; }
[ "$leftover" -eq 0 ] && ok "all app-layer services down"

if [ "$WITH_INFRA" -eq 1 ]; then
  say "Stopping Postgres + Redis (Homebrew)…"
  brew services stop postgresql@16 >/dev/null 2>&1 && ok "postgresql@16 stopped" || info "postgresql@16 not running"
  brew services stop redis         >/dev/null 2>&1 && ok "redis stopped"         || info "redis not running"
else
  info "Postgres + Redis left running (use --with-infra to stop them)"
fi
