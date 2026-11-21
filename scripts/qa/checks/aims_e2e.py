"""End-to-end loop on the AIMS training fixture with the TEST-ONLY driver doing the clicks.

Proves step progression and completion detection. It does not prove a person can follow
the pointer: that stays a needs-human check.
"""
import json
import signal
import subprocess
import time

from _common import PY, ROOT, result, sh, wait_for

FEATURE = "companion-loop"
QUESTION = "എന്റെ നെല്ല് വെള്ളപ്പൊക്കത്തിൽ നശിച്ചു, ഇൻഷുറൻസ് ക്ലെയിം എങ്ങനെ ചെയ്യാം?"


def run():
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]
    import importlib.util
    spec = importlib.util.spec_from_file_location("drive", ROOT / "scripts" / "drive_training.py")
    drive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drive)

    sh("sh", "scripts/restart_training.sh")
    wait_for(lambda: reader.find_app(drive.BUNDLE))
    time.sleep(1.5)
    before = set((ROOT / "runs").glob("session-*.jsonl"))
    app = subprocess.Popen([PY, "-m", "companion.app", "--question", QUESTION], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        log = wait_for(lambda: next(iter(set((ROOT / "runs").glob("session-*.jsonl")) - before), None), 10)
        if log is None:
            return [result(FEATURE, "companion start", "fail", "live-machine", app.stderr.read()[-500:] if app.poll() else "no session log")]
        time.sleep(1.5)
        d = sh(PY, "scripts/drive_training.py", "--delay", "1.2", timeout=90)
        time.sleep(2.0)
    finally:
        app.send_signal(signal.SIGTERM)
        app.wait(timeout=5)

    events = [json.loads(l) for l in log.read_text().splitlines()]
    decisions = [e for e in events if e["event"] == "decision"]
    targets = [e["target"] or e["kind"] for e in decisions]
    expected = drive.ORDER + ["complete"]
    complete = next((e for e in events if e["event"] == "complete"), None)
    invalid = [e for e in decisions if not e["valid"]]
    obs = [e["observe_ms"] for e in decisions]
    return [
        result(FEATURE, "step sequence matches task", "pass" if targets == expected else "fail", "live-machine",
               f"{len(targets)} decisions" if targets == expected else f"got {targets} expected {expected}; driver stderr tail: {d.stderr.strip().splitlines()[-1] if d.stderr.strip() else 'none'}"),
        result(FEATURE, "every pointer validated", "fail" if invalid else "pass", "live-machine",
               f"rejected: {[(e['target'], e['reason']) for e in invalid]}" if invalid else "all decisions passed validation"),
        result(FEATURE, "completion verified (status + fresh receipt)",
               "pass" if complete and complete.get("receipt_file_fresh") else "fail", "live-machine", str(complete)),
        result(FEATURE, "observe latency", "pass" if obs and max(obs) < 250 else "fail", "live-machine",
               f"max {max(obs):.0f} ms, median {sorted(obs)[len(obs)//2]:.0f} ms" if obs else "no data"),
        result(FEATURE, "person follows pointer and clicks", "skip", "needs-human",
               "driver clicked, not a person; see features/companion-loop.md checklist"),
    ]
