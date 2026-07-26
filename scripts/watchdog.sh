#!/usr/bin/env bash
# Overnight watchdog: health checks, auto-restarts, escalate code bugs to agent.
# Exit 0 = healthy (or auto-fixed). Exit 2 = needs agent (emits tick line on stdout when --tick).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/data/watchdog" "$ROOT/autoresearch"
LOG="$ROOT/data/watchdog/watchdog.log"
STATUS="$ROOT/data/watchdog/status.txt"
PIDDIR="$ROOT/data/watchdog"
EMIT_TICK=0
[[ "${1:-}" == "--tick" ]] && EMIT_TICK=1

ts() { date -u +%Y-%m-%dT%H:%MZ; }
log() { echo "$(ts) $*" | tee -a "$LOG"; }

needs_agent=0
agent_reasons=()

mark_agent() {
  needs_agent=1
  agent_reasons+=("$1")
  log "NEEDS_AGENT: $1"
}

ensure_compose() {
  local svc="$1"
  if ! docker compose ps --status running -q "$svc" 2>/dev/null | grep -q .; then
    log "RESTART: $svc not running"
    docker compose up -d --build "$svc" >>"$LOG" 2>&1 || true
    sleep 2
    if ! docker compose ps --status running -q "$svc" 2>/dev/null | grep -q .; then
      mark_agent "compose service $svc failed to start"
    else
      log "OK: restarted $svc"
    fi
  else
    log "OK: $svc running"
  fi
}

check_trader_tracebacks() {
  local lines
  lines="$(docker logs --since 30m intelligent-trader 2>&1 | tail -n 200 || true)"
  if echo "$lines" | grep -qE 'Traceback \(most recent call last\)|^ERROR |Exception:'; then
    # Ignore one-off network flakes unless repeated
    local count
    count="$(echo "$lines" | grep -cE 'Traceback \(most recent call last\)' || true)"
    if [[ "${count:-0}" -ge 2 ]]; then
      mark_agent "intelligent-trader repeated Traceback in last 30m (count=$count)"
    else
      log "WARN: trader traceback seen once (watching)"
    fi
  fi
}

check_ollama() {
  if curl -sf --max-time 3 "http://127.0.0.1:11434/api/tags" >/dev/null; then
    log "OK: ollama reachable"
  else
    mark_agent "ollama not reachable at 127.0.0.1:11434 — start ollama serve"
  fi
}

check_openbb_http() {
  if curl -sf --max-time 3 "http://127.0.0.1:7779/health" >/dev/null \
    || curl -sf --max-time 3 "http://127.0.0.1:7779/" >/dev/null \
    || curl -sf --max-time 3 "http://127.0.0.1:7779/widgets.json" >/dev/null; then
    log "OK: openbb-backend HTTP"
  else
    log "RESTART: openbb-backend HTTP failed"
    docker compose up -d --build openbb-backend >>"$LOG" 2>&1 || true
    sleep 2
    if ! curl -sf --max-time 3 "http://127.0.0.1:7779/widgets.json" >/dev/null; then
      mark_agent "openbb-backend HTTP still down after restart"
    fi
  fi
}

ensure_ollama_loop() {
  if pgrep -f 'run_ollama_autoresearch_loop.sh' >/dev/null 2>&1; then
    log "OK: ollama autoresearch loop"
    return
  fi
  log "RESTART: ollama autoresearch loop"
  nohup env OLLAMA_AUTOSEARCH_PUSH=1 bash "$ROOT/scripts/run_ollama_autoresearch_loop.sh" \
    >>"$PIDDIR/ollama_loop.out" 2>&1 &
  echo $! >"$PIDDIR/ollama_loop.pid"
  sleep 1
  if pgrep -f 'run_ollama_autoresearch_loop.sh' >/dev/null 2>&1; then
    log "OK: ollama loop restarted pid=$(cat "$PIDDIR/ollama_loop.pid")"
  else
    mark_agent "failed to restart ollama autoresearch loop"
  fi
}

ensure_shell_loop() {
  # $1=pattern $2=name $3=command to start
  local pattern="$1" name="$2"
  shift 2
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    log "OK: $name loop"
    return
  fi
  log "RESTART: $name loop"
  nohup bash -c "$*" >>"$PIDDIR/${name}.out" 2>&1 &
  echo $! >"$PIDDIR/${name}.pid"
  sleep 1
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    log "OK: $name loop restarted"
  else
    mark_agent "failed to restart $name loop"
  fi
}

# --- run checks ---
log "=== watchdog start ==="
ensure_compose intelligent-trader
ensure_compose openbb-backend
check_openbb_http
check_trader_tracebacks
check_ollama
ensure_ollama_loop

ensure_shell_loop 'run_improve_loop.sh|AGENT_LOOP_TICK_improve' improve \
  "bash '$ROOT/scripts/run_improve_loop.sh'"

ensure_shell_loop 'AGENT_LOOP_TICK_docs' docs \
  'while true; do sleep 604800; echo '"'"'AGENT_LOOP_TICK_docs {"prompt":"WEEKLY DOCS UPDATE. Follow DOCS_MAINTENANCE.md. Fix stale docs. Commit+push. Short status."}'"'"'; done'

{
  echo "time=$(ts)"
  echo "needs_agent=$needs_agent"
  echo "reasons=${agent_reasons[*]:-none}"
} >"$STATUS"

if [[ "$needs_agent" -eq 1 ]]; then
  reason_joined="$(IFS='; '; echo "${agent_reasons[*]}")"
  log "=== watchdog NEEDS_AGENT ==="
  if [[ "$EMIT_TICK" -eq 1 ]]; then
    echo "AGENT_LOOP_TICK_watchdog {\"prompt\":\"WATCHDOG ALERT (CEST overnight). NEVER ask the human. Status: ${reason_joined}. Read data/watchdog/status.txt and data/watchdog/watchdog.log and recent docker logs for intelligent-trader/openbb-backend. Fix the bug or infra issue, verify with docker pytest offline and docker compose ps, commit+push per GIT.md, restart services/loops as needed. Update IMPROVEMENT.md if relevant. Short status only.\"}"
  fi
  exit 2
fi

log "=== watchdog healthy ==="
exit 0
