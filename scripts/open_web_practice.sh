#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
url="http://127.0.0.1:${CONDUCTOR_PORT:-8765}"
workspace_key="$(.venv/bin/python -c 'from scripts.serve_web_practice import WORKSPACE_KEY; print(WORKSPACE_KEY.decode())')"
health() { curl --noproxy '*' -fsS --max-time 1 "$url/health" 2>/dev/null || true; }

mkdir -p runs
if [ "$(health)" != "$workspace_key" ]; then
    nohup .venv/bin/python scripts/serve_web_practice.py >runs/web-practice-server.log 2>&1 </dev/null &
    attempt=0
    until [ "$(health)" = "$workspace_key" ]; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 20 ]; then
            echo "Practice server unavailable at $url; check runs/web-practice-server.log or set CONDUCTOR_PORT." >&2
            exit 1
        fi
        sleep .1
    done
fi

rm -f runs/web-practice-complete.json
osascript - "$url/" <<'APPLESCRIPT'
on run argv
    tell application id "com.apple.Safari"
        make new document with properties {URL:item 1 of argv}
        activate
    end tell
end run
APPLESCRIPT
