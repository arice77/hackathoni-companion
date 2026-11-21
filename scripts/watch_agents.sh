#!/bin/sh
# Print one line whenever a Conductor session started by the given orchestrator session changes status
# (working -> idle / error / waiting...). Reads Conductor's local DB read-only. Run it under Claude Code's
# Monitor tool so each line arrives as a notification:  scripts/watch_agents.sh <orchestrator-session-id>
DB="$HOME/Library/Application Support/com.conductor.app/conductor.db"
ME="${1:?orchestrator session id}"
q() { sqlite3 -readonly "file:$DB?mode=ro" "select id||'|'||status||'|'||title from sessions where created_by_session_id='$ME' and closed_at is null;" 2>/dev/null || true; }
prev=$(q)
while true; do
  sleep 10
  cur=$(q)
  [ -z "$cur" ] && continue
  echo "$cur" | while IFS='|' read -r id st title; do
    old=$(echo "$prev" | awk -F'|' -v i="$id" '$1==i{print $2}')
    [ "$old" != "$st" ] && echo "AGENT ${old:-new} -> $st : $title ($id)"
  done
  prev=$cur
done
