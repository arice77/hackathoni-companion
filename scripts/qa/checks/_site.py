"""Helpers for the real-site follow-the-pointer checks (YouTube, Gmail).

The check opens ONE new Safari window of its own, with unusual bounds so the driver can tell it apart, and
closes that window (by its AppleScript id, and only while it still shows the site's host) when done. Other
Safari windows and tabs are never addressed. Nothing here prints addresses, subjects, senders or bodies.
"""
import re
import signal
import subprocess
import time

from _common import PY, ROOT, result, sh, wait_for
import _follow

SAFARI = "com.apple.Safari"
BOUNDS = (63, 41, 1253, 1041)  # tall, and unusual on purpose: the driver finds our window by its exact bounds
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def pack_landed(site: str, module_name: str) -> str | None:
    """None when the site pack is on this branch and registered with a start_guidance hook; else the reason."""
    pack = ROOT / "companion" / "sites" / f"{module_name}.py"
    if not pack.exists():
        return f"companion/sites/{module_name}.py is not on this branch yet (the {site} pack is still being built)"
    registry = (ROOT / "companion" / "sites" / "__init__.py").read_text()
    if module_name not in registry:
        return f"companion/sites/{module_name}.py exists but is not registered in companion/sites/__init__.py"
    if "start_guidance" not in pack.read_text():
        return f"the {site} pack has no start_guidance hook yet"
    return None


def _osa(script: str, timeout: int = 30):
    return sh("osascript", "-e", script, timeout=timeout)


def open_own_window(url: str, host: str):
    """Open a new Safari window at `url`, set BOUNDS, raise it. Returns (window_id, (l,t,r,b), error)."""
    l, t, r, b = BOUNDS
    script = f'''
tell application id "{SAFARI}"
    make new document with properties {{URL:"{url}"}}
    activate
    delay 1
    set w to front window
    set bounds of w to {{{l}, {t}, {r}, {b}}}
    delay 0.6
    set bb to bounds of w
    return (id of w as string) & "," & (item 1 of bb as string) & "," & (item 2 of bb as string) & "," & (item 3 of bb as string) & "," & (item 4 of bb as string) & "," & (URL of current tab of w)
end tell'''
    p = _osa(script, 45)
    if p.returncode != 0:
        return None, None, f"could not open a Safari window: {p.stderr.strip()[:200]}"
    wid, *nums, shown = p.stdout.strip().split(",", 5)
    if host not in shown:
        # Close nothing: this window might not be ours. Report and stop.
        return None, None, f"the new front Safari window did not show {host}; left untouched"
    return int(wid), tuple(int(n) for n in nums), None


def close_own_window(wid: int | None, host: str) -> str:
    """Close window `wid` only while it has one tab that still shows `host`."""
    if wid is None:
        return "no window to close"
    script = f'''
tell application id "{SAFARI}"
    try
        set w to window id {wid}
        if (count of tabs of w) is 1 and (URL of current tab of w) contains "{host}" then
            close w
            return "closed"
        end if
        return "kept (tabs changed or other site)"
    on error
        return "already gone"
    end try
end tell'''
    p = _osa(script)
    return p.stdout.strip() if p.returncode == 0 else f"close failed: {p.stderr.strip()[:120]}"


def run_walk(*, site: str, url: str, host: str, ready_prefix: str, question: str, driver_args: list[str], task: str = "web_site",
             total_timeout: int = 240, decision_timeout: int = 45):
    """Open our window, start the companion, run the driver, tear everything down.

    Returns (error_results | None, ctx) where ctx has records, rc, stderr, started, out_file, log, window id.
    """
    import json
    from companion import reader
    wid, bounds, err = open_own_window(url, host)
    if err:
        return [result(_FEATURE, f"{site} dedicated Safari window ready", "blocked", "live-machine", err)], None
    app = None
    try:
        ready = wait_front_readable(ready_prefix)
        if ready:
            return [result(_FEATURE, f"{site} page readable in the dedicated window", "blocked", "live-machine", ready)], None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out_file = ROOT / "runs" / f"{site}-follow-{stamp}.jsonl"
        before = set((ROOT / "runs").glob("session-*.jsonl"))
        started = time.time()
        app = subprocess.Popen([PY, "-m", "companion.app", "--task", task, "--mute", "--question", question],
                               cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        log = wait_for(lambda: next(iter(set((ROOT / "runs").glob("session-*.jsonl")) - before), None), 10)
        if log is None:
            return [result(_FEATURE, "companion start", "fail", "live-machine",
                           app.stderr.read()[-500:] if app.poll() is not None else "no session log within 10 s")], None
        cmd = [PY, "scripts/drive_follow_site.py", "--site", site, "--bounds", ",".join(map(str, bounds)),
               "--log", str(log), "--out", str(out_file), "--companion-pid", str(app.pid),
               "--decision-timeout", str(decision_timeout), "--total-timeout", str(total_timeout), *driver_args]
        d = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=total_timeout + 60)
        time.sleep(1.0)
        records = [json.loads(l) for l in out_file.read_text().splitlines()] if out_file.exists() else []
        return None, {"records": records, "rc": d.returncode, "stderr": d.stderr, "started": started,
                      "out_file": out_file, "log": log}
    finally:
        if app is not None:
            app.send_signal(signal.SIGTERM)
            try:
                app.wait(timeout=5)
            except subprocess.TimeoutExpired:
                app.kill()
        print(f"[{site}] dedicated window: {close_own_window(wid, host)}", flush=True)


_FEATURE = "web-support"


def wait_front_readable(prefix: str, seconds: float = 25.0) -> str | None:
    import _web
    return _web.wait_front_readable(prefix, seconds=seconds)


# ---- shared assessment pieces ------------------------------------------------------------------------
def points(records, phase=None):
    return [r for r in records if r["event"] == "decision" and r["kind"] == "point"
            and (phase is None or r.get("phase") == phase)]


def order_check(pts, steps):
    """steps: [(name, predicate(rec))]. Each must be pointed at, first occurrences strictly in this order.
    Returns (ok, detail)."""
    first = {}
    for pos, rec in enumerate(pts):
        for i, (_, pred) in enumerate(steps):
            if i not in first and pred(rec):
                first[i] = pos
    missing = [steps[i][0] for i in range(len(steps)) if i not in first]
    ordered = [first[i] for i in range(len(steps)) if i in first]
    ok = not missing and ordered == sorted(ordered) and len(set(ordered)) == len(ordered)
    seq = [f"{r.get('target_role')}:{r.get('target_label')}" for r in pts]
    return ok, f"targets {seq}; missing {missing}; first positions {first}"


def repeats(pts, by_phase=True, allow=None):
    """Targets pointed at more than once. `allow` maps a lower-case label to the number of EXTRA pointers tolerated
    (e.g. {"settings": 1}: one intentional retry)."""
    allow = allow or {}
    seen, out = {}, []
    for r in pts:
        k = (r.get("phase") if by_phase else None, r.get("target_role"), r.get("target_label"))
        seen[k] = seen.get(k, 0) + 1
        if seen[k] == 2 + allow.get((k[2] or "").strip().lower(), 0):
            out.append(k[2])
    return out


def decision_list(records, redact=None):
    lines = []
    for r in records:
        if r["event"] != "decision":
            continue
        text = _follow.line(r)
        lines.append(f"[q{r.get('phase')}] " + (redact(text) if redact else text))
    return "\n".join(lines)


def stop_of(records, rc, err):
    return next((r for r in records if r["event"] == "stop"),
                {"reason": f"driver produced no summary (rc={rc}): {err[-200:]}", "phases": {}})
