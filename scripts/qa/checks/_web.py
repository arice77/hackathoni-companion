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

def _close_script(url):
    return f'''
tell application id "{SAFARI}"
    set closed to 0
    repeat with w in (reverse of (get every window))
        try
            if (count of tabs of w) is 1 then
                if URL of tab 1 of w is "{url}" then
                    close w
                    set closed to closed + 1
                end if
            else
                repeat with t in (reverse of (get every tab of w))
                    if URL of t is "{url}" then
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


def close_practice_windows(url: str = URL) -> str:
    """Close only Safari windows/tabs whose URL is exactly `url` (default: this workspace's practice root)."""
    p = sh("osascript", "-e", _close_script(url), timeout=30)
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


# ---- pizza page (follow-the-pointer) -------------------------------------------------------------
PIZZA_URL = f"http://127.0.0.1:{PORT}/pizza"


def _http(path, method="GET"):
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # loopback, never via a proxy
    try:
        with opener.open(req, timeout=2) as r:
            return r.status, r.read()
    except Exception as exc:  # noqa: BLE001 - HTTPError, refused connection, timeout
        return getattr(exc, "code", 0), b""


def ensure_pizza_route() -> str | None:
    """Make sure this workspace's practice server serves /pizza; restart our own stale server if not.

    Only a server that answers /health with this workspace's key AND whose cwd is this workspace is stopped.
    Returns an error string or None.
    """
    import subprocess
    from scripts.serve_web_practice import WORKSPACE_KEY
    status, _ = _http("/pizza")
    if status == 200:
        return None
    health, body = _http("/health")
    if health == 200 and body != WORKSPACE_KEY:
        return f"port {PORT} is served by another workspace's practice server; not touching it"
    if health == 200:
        pids = sh("lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-t").stdout.split()
        for pid in pids:
            cwd = sh("lsof", "-a", "-p", pid, "-d", "cwd", "-Fn").stdout
            if f"n{ROOT}\n" in cwd + "\n":
                sh("kill", pid)
        time.sleep(1)
    (ROOT / "runs").mkdir(exist_ok=True)
    log = open(ROOT / "runs" / "web-practice-server.log", "a")
    subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "scripts/serve_web_practice.py"], cwd=ROOT,
                     stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    ok = wait_for(lambda: _http("/pizza")[0] == 200, seconds=8)
    return None if ok else "practice server does not serve /pizza (check runs/web-practice-server.log)"


def open_pizza_front() -> str | None:
    """Close our stale pizza windows, open one fresh pizza window and bring Safari to the front.

    Returns an error string or None. Other Safari windows are left alone (the new one simply sits in front).
    """
    from companion import reader
    (ROOT / "runs" / "pizza-complete.json").unlink(missing_ok=True)
    close_practice_windows(PIZZA_URL)
    time.sleep(0.5)
    script = (f'tell application id "{SAFARI}"\n make new document with properties {{URL:"{PIZZA_URL}"}}\n activate\nend tell')
    p = sh("osascript", "-e", script, timeout=30)
    if p.returncode != 0:
        return f"could not open the pizza page in Safari: {p.stderr.strip()[:200]}"

    def front():
        try:
            reader.snapshot(SAFARI, page_url_prefix=PIZZA_URL)  # raises unless the front window's selected page is ours
            return True
        except reader.ReaderError:
            return False
    if not wait_for(front, seconds=15):
        return "the pizza page did not become the front Safari window's selected page (someone else took focus?)"
    return None
