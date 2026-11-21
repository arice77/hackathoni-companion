"""Setup and teardown of the web practice page in Safari for QA checks.

Touches only Safari windows or tabs whose URL is exactly this workspace's practice URL
(http://127.0.0.1:$CONDUCTOR_PORT/). Other windows, tabs, other workspaces' ports and any
other browser are never addressed.
"""
import os
import time

from _common import ROOT, sh, wait_for

SAFARI = "com.apple.Safari"
PORT = os.environ.get("CONDUCTOR_PORT") or "8765"
URL = f"http://127.0.0.1:{PORT}/"

_CLOSE = f'''
tell application id "{SAFARI}"
    set closed to 0
    repeat with w in (reverse of (get every window))
        try
            if (count of tabs of w) is 1 then
                if URL of tab 1 of w is "{URL}" then
                    close w
                    set closed to closed + 1
                end if
            else
                repeat with t in (reverse of (get every tab of w))
                    if URL of t is "{URL}" then
                        close t
                        set closed to closed + 1
                    end if
                end repeat
            end if
        end try
    end repeat
    return closed
end tell
'''


def close_practice_windows() -> str:
    p = sh("osascript", "-e", _CLOSE, timeout=30)
    return p.stdout.strip() if p.returncode == 0 else f"osascript failed: {p.stderr.strip()[:200]}"


def open_fresh_page(drive) -> str | None:
    """Close our stale practice windows, open exactly one fresh page. Returns an error or None."""
    close_practice_windows()
    time.sleep(0.5)
    p = sh("sh", "scripts/open_web_practice.sh", timeout=60)
    if p.returncode != 0:
        return f"open_web_practice.sh failed: {(p.stderr or p.stdout).strip()[:300]}"
    ok = wait_for(lambda: len(drive.web_areas()) == 1 and _ready(drive), seconds=15)
    if not ok:
        return f"practice page not readable in Safari ({len(drive.web_areas())} matching web areas)"
    return None


def _ready(drive) -> bool:
    try:
        drive.element_for("business-name")
        return True
    except SystemExit:
        return False


def load_drive():
    import importlib.util
    spec = importlib.util.spec_from_file_location("drive_web_practice", ROOT / "scripts" / "drive_web_practice.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
