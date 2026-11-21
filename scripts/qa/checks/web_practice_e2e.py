"""End-to-end loop on the web practice page in Safari with the TEST-ONLY driver doing the input.

The companion is launched with --mute (no Sarvam TTS) and --task web_practice, and a typed
question (no STT), so this check spends no Sarvam credits. Proves step progression and
completion detection; it does not prove a person can follow the pointer.
"""
import json
import signal
import subprocess
import time

from _common import PY, ROOT, result, sh, wait_for
import _web

FEATURE = "web-support"
QUESTION = "ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?"
# The driver types the name, then the page's sample button fills district + category together,
# so the pointer legitimately skips from district straight to Next.
EXPECTED = ["business-name", "district", "details-next", "attach-sample", "documents-next",
            "declaration", "save", "complete"]


def run():
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]
    drive = _web.load_drive()
    err = _web.open_fresh_page(drive)
    if err:
        return [result(FEATURE, "web practice page opens in Safari", "fail", "live-machine", err)]
    receipt = ROOT / "runs" / "web-practice-complete.json"
    before = set((ROOT / "runs").glob("session-*.jsonl"))
    app = subprocess.Popen([PY, "-m", "companion.app", "--mute", "--task", "web_practice", "--question", QUESTION],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        log = wait_for(lambda: next(iter(set((ROOT / "runs").glob("session-*.jsonl")) - before), None), 10)
        if log is None:
            return [result(FEATURE, "companion start", "fail", "live-machine",
                           app.stderr.read()[-500:] if app.poll() is not None else "no session log within 10 s")]
        time.sleep(1.5)
        d = sh(PY, "scripts/drive_web_practice.py", "--delay", "1.5", timeout=90)
        time.sleep(2.5)
    finally:
        app.send_signal(signal.SIGTERM)
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()
        stderr_tail = app.stderr.read()[-300:] if app.stderr else ""
        _web.close_and_settle()

    events = [json.loads(line) for line in log.read_text().splitlines()]
    decisions = [e for e in events if e["event"] == "decision"]
    targets = [e["target"] or e["kind"] for e in decisions]
    complete = next((e for e in events if e["event"] == "complete"), None)
    invalid = [e for e in decisions if not e["valid"]]
    reader_errors = [e for e in events if e["event"] == "reader_error"]
    obs = sorted(e["observe_ms"] for e in decisions)
    drv = d.stderr.strip().splitlines()[-1] if d.stderr.strip() else "none"
    try:
        body = json.loads(receipt.read_text())
        receipt_ok = body.get("task") == "web_practice" and body.get("synthetic") is True \
            and set(body) == {"task", "synthetic", "completed_at"}
        receipt_detail = f"keys {sorted(body)}"
    except (OSError, ValueError) as exc:
        receipt_ok, receipt_detail = False, f"receipt unreadable: {exc}"
    fresh = bool(complete and complete.get("receipt_file_fresh"))
    return [
        result(FEATURE, "step sequence matches task", "pass" if targets == EXPECTED else "fail", "live-machine",
               f"{len(targets)} decisions; {len(reader_errors)} reader pauses" if targets == EXPECTED else
               f"got {targets} expected {EXPECTED}; reader_errors {[e['error'][:80] for e in reader_errors]}; "
               f"driver rc={d.returncode} tail: {drv}; companion stderr: {stderr_tail.strip()[-150:]}; log {log}"),
        result(FEATURE, "every pointer validated", "fail" if invalid or not decisions else "pass", "live-machine",
               f"rejected: {[(e['target'], e['reason']) for e in invalid]}" if invalid else
               f"all {len(decisions)} decisions passed validation"),
        result(FEATURE, "completion verified (status + fresh receipt)",
               "pass" if complete and fresh and receipt_ok else "fail", "live-machine",
               f"{complete}; {receipt_detail}; log {log}"),
        result(FEATURE, "observe latency", "pass" if obs and obs[-1] < 250 else "fail", "live-machine",
               f"max {obs[-1]:.0f} ms, median {obs[len(obs)//2]:.0f} ms (limit 250)" if obs else "no data"),
        result(FEATURE, "person follows pointer and clicks in the browser", "skip", "needs-human",
               "driver typed/pressed, not a person; see features/web-support.md checklist"),
    ]
