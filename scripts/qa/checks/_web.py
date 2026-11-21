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


def _count_open(url: str) -> int:
    script = (f'tell application id "{SAFARI}"\n set n to 0\n repeat with w in (get every window)\n try\n'
              f' repeat with t in (get every tab of w)\n if URL of t is "{url}" then set n to n + 1\n end repeat\n'
              f' end try\n end repeat\n return n\nend tell')
    p = sh("osascript", "-e", script, timeout=30)
    return int(p.stdout.strip() or 0) if p.returncode == 0 and p.stdout.strip().isdigit() else -1


def close_and_settle(url: str = URL) -> None:
    """Close our window(s) for `url`, then wait until Safari really has none and its AX tree has settled.

    The next web check starts from a quiet Safari: right after a close, Safari briefly reports a front window
    with no readable bounds, which made the next check's first reads (and driver lookup) fail.
    """
    close_practice_windows(url)
    wait_for(lambda: _count_open(url) == 0, seconds=6, every=0.3)
    time.sleep(0.8)


def wait_front_readable(url: str, title: str | None = None, seconds: float = 20.0) -> str | None:
    """Wait until OUR page is the front window's selected page and the reader gets it twice in a row, 0.6 s apart,
    with controls. `title` pins the practice root page (a plain prefix match on `/` would also match `/pizza`).
    Returns an error string or None."""
    from companion import reader
    state = {"streak": 0, "last": "no read yet"}

    def good():
        try:
            snap = reader.snapshot(SAFARI, page_url_prefix=url)
        except reader.ReaderError as exc:
            state["streak"], state["last"] = 0, str(exc)
            return False
        if (title and snap.window_title != title) or not snap.controls:
            state["streak"], state["last"] = 0, f"front page is {snap.window_title!r} with {len(snap.controls)} controls"
            return False
        state["streak"] += 1
        time.sleep(0.6)
        return state["streak"] >= 2

    if wait_for(good, seconds=seconds, every=0.2):
        return None
    return f"{url} did not become the front, readable Safari page within {seconds:.0f} s (last: {state['last']})"


def _open_in_safari(url: str) -> str | None:
    script = f'tell application id "{SAFARI}"\n make new document with properties {{URL:"{url}"}}\n activate\nend tell'
    p = sh("osascript", "-e", script, timeout=30)
    return None if p.returncode == 0 else f"could not open {url} in Safari: {p.stderr.strip()[:200]}"


def open_fresh_page(drive) -> str | None:
    """Close our stale practice windows, open exactly one fresh page, and wait until it is front and readable
    by both the reader and the test driver. Returns an error or None."""
    from companion import reader
    close_and_settle(URL)
    p = sh("sh", "scripts/open_web_practice.sh", timeout=60)
    if p.returncode != 0:
        return f"open_web_practice.sh failed: {(p.stderr or p.stdout).strip()[:300]}"
    ok = wait_for(lambda: len(drive.web_areas()) == 1 and _ready(drive), seconds=15)
    if not ok:
        return f"practice page not readable in Safari ({len(drive.web_areas())} matching web areas)"
    return wait_front_readable(URL, title=reader.PRACTICE_TITLE)


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


# ---- local site copies (pizza, KSEB) for follow-the-pointer ---------------------------------------
PIZZA_URL = f"http://127.0.0.1:{PORT}/pizza"
KSEB_URL = f"http://127.0.0.1:{PORT}/kseb-quickpay"


def _http(path, method="GET"):
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # loopback, never via a proxy
    try:
        with opener.open(req, timeout=2) as r:
            return r.status, r.read()
    except Exception as exc:  # noqa: BLE001 - HTTPError, refused connection, timeout
        return getattr(exc, "code", 0), b""


def ensure_route(path: str) -> str | None:
    """Make sure this workspace's practice server serves `path`; restart our own stale server if not.

    Only a server that answers /health with this workspace's key AND whose cwd is this workspace is stopped.
    Returns an error string or None.
    """
    import subprocess
    from scripts.serve_web_practice import WORKSPACE_KEY
    status, _ = _http(path)
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
    ok = wait_for(lambda: _http(path)[0] == 200, seconds=8)
    return None if ok else f"practice server does not serve {path} (check runs/web-practice-server.log)"


def ensure_pizza_route() -> str | None:
    return ensure_route("/pizza")


def open_site_front(url: str, receipt: str) -> str | None:
    """Close our stale window for `url`, clear the old receipt, open one fresh window, and wait until it is the
    front window's selected page and readable. Other Safari windows are left alone."""
    (ROOT / "runs" / receipt).unlink(missing_ok=True)
    close_and_settle(url)
    return _open_in_safari(url) or wait_front_readable(url)


def open_pizza_front() -> str | None:
    return open_site_front(PIZZA_URL, "pizza-complete.json")
