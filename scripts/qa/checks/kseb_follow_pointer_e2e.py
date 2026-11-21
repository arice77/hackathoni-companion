"""Follow-the-pointer e2e on a local copy of KSEB Quick Pay (/kseb-quickpay), Malayalam question, Sarvam planner.

LIVE + SARVAM (about 10-15 chat calls). BLOCKED unless QA_LIVE_SARVAM=1, a SARVAM_API_KEY exists, and the
`web_site` task exists (companion/tasks/web_site.py, being built by the planner builder).

Question: "എന്റെ കറന്റ് ബിൽ എങ്ങനെ അടയ്ക്കാം?" (How do I pay my electricity bill?). The test-only driver
(scripts/drive_follow_pointer.py --page kseb) acts only on the control the companion points at: it types
synthetic 1234567890123, 9000000000 and PRACTICE (the practice image's fixed text), never follows links, and
clicks the button. The practice bill replaces the form, as on the real site. Real KSEB is never contacted.
"""
import json
import os
import re
import signal
import subprocess
import time

from _common import PY, ROOT, result, wait_for
import _follow
import _web

FEATURE = "web-support"
QUESTION = "എന്റെ കറന്റ് ബിൽ എങ്ങനെ അടയ്ക്കാം?"
TASK = "web_site"
# keyword per step; matched against the pointed control's label
STEPS = [("consumer no.", "consumer"), ("mobile", "mobile"), ("captcha text", "text shown"), ("submit", "submit")]
DETOUR = re.compile(r"refresh|\bhere\b|^home$|quick pay|register complaint|complaint status", re.IGNORECASE)
READ_VERB = re.compile(r"\b(read|look|see|copy|type)\b", re.IGNORECASE)
IMAGE_WORD = re.compile(r"\b(image|picture|captcha|letters|characters)\b", re.IGNORECASE)
ORIENTATION = re.compile(r"\bthis is (?:an?|the) [^.]{0,40}(?:form|page|site|website)\b", re.IGNORECASE)
RECEIPT = ROOT / "runs" / "kseb-complete.json"
STATUS_TEXT = "Bill Details (practice)"
CAPTCHA_TEXT = "PRACTICE"


def _task_exists() -> bool:
    return (ROOT / "companion" / "tasks" / f"{TASK}.py").exists()


def run():
    name = "kseb follow-the-pointer (Sarvam planner, Malayalam question)"
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, name, "blocked", "blocked",
                       "set QA_LIVE_SARVAM=1: live Sarvam planner (~10-15 chat calls) and it puts a Safari window in front")]
    if not _task_exists():
        return [result(FEATURE, name, "blocked", "blocked",
                       f"task `{TASK}` does not exist yet (companion/tasks/{TASK}.py): the planner builder's work is pending. "
                       "The page, driver and assertions are ready and self-tested")]
    if not _follow.key_available():
        return [result(FEATURE, name, "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]

    err = _web.ensure_route("/kseb-quickpay") or _web.open_site_front(_web.KSEB_URL, "kseb-complete.json")
    if err:
        return [result(FEATURE, "KSEB practice page ready in front Safari window", "blocked", "live-machine", err)]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_file = ROOT / "runs" / f"kseb-follow-{stamp}.jsonl"
    before = set((ROOT / "runs").glob("session-*.jsonl"))
    started = time.time()
    app = subprocess.Popen([PY, "-m", "companion.app", "--task", TASK, "--mute", "--question", QUESTION],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        log = wait_for(lambda: next(iter(set((ROOT / "runs").glob("session-*.jsonl")) - before), None), 10)
        if log is None:
            return [result(FEATURE, "companion start", "fail", "live-machine",
                           app.stderr.read()[-500:] if app.poll() is not None else "no session log within 10 s")]
        d = subprocess.run([PY, "scripts/drive_follow_pointer.py", "--page", "kseb", "--log", str(log),
                            "--out", str(out_file), "--decision-timeout", "40", "--total-timeout", "240"],
                           cwd=ROOT, capture_output=True, text=True, timeout=300)
        time.sleep(1.0)
        heading = _follow.heading_seen("kseb", STATUS_TEXT)
    finally:
        app.send_signal(signal.SIGTERM)
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()
        _web.close_and_settle(_web.KSEB_URL)

    records = [json.loads(l) for l in out_file.read_text().splitlines()] if out_file.exists() else []
    return assess(records, d.returncode, d.stderr, heading, started, out_file, log)


def _step_index(label: str):
    low = (label or "").lower()
    return next((i for i, (_, kw) in enumerate(STEPS) if kw in low), None)


def assess(records, driver_rc, driver_err, heading_seen, started, out_file, log):
    decisions = [r for r in records if r["event"] == "decision"]
    stop = next((r for r in records if r["event"] == "stop"), {"reason": f"driver produced no summary (rc={driver_rc}): {driver_err[-200:]}"})
    reader_errors = [r for r in records if r["event"] == "reader_error"]
    points = [r for r in decisions if r["kind"] == "point"]
    labels = [r.get("target_label") for r in points]
    full_list = "\n".join(_follow.line(r) for r in decisions)
    print(f"\n--- kseb follow-the-pointer: {len(decisions)} decisions, stop={stop['reason']} ---\n{full_list}\n--- end ---")
    where = f"decision list: {out_file}; session log: {log}"

    # 1 order: consumer -> mobile -> captcha -> submit, each pointed at, strictly in that order
    first = {}
    for pos, label in enumerate(labels):
        i = _step_index(label)
        if i is not None:
            first.setdefault(i, pos)
    missing = [STEPS[i][0] for i in range(len(STEPS)) if i not in first]
    in_order = not missing and [first[i] for i in range(len(STEPS))] == sorted(first.values())
    detail = f"targets {labels}; missing {missing}; first positions {dict(sorted(first.items()))}; {where}"
    results = [result(FEATURE, "steps pointed in order: consumer no, mobile, captcha text, submit",
                      "pass" if in_order else "fail", "live-machine",
                      detail if in_order else f"{detail}\nDECISIONS:\n{full_list}")]

    # 2 captcha guidance: tell the user to read the image, never guess the text
    cap = [r for r in points if _step_index(r.get("target_label")) == 2]
    if not cap:
        results.append(result(FEATURE, "captcha guidance tells the user to read the image", "fail", "live-machine",
                              "the captcha field was never pointed at"))
    else:
        text = cap[0].get("instruction_en", "")
        ok = bool(READ_VERB.search(text) and IMAGE_WORD.search(text)) and CAPTCHA_TEXT.lower() not in text.lower()
        results.append(result(FEATURE, "captcha guidance tells the user to read the image", "pass" if ok else "fail", "live-machine",
                              f"instruction: \"{text}\"" + ("" if ok else " (needs a read/look/type verb, the image, and must not state the text)")))

    # 3 repeats
    seen, repeats = {}, []
    for r in points:
        k = (r.get("target_role"), r.get("target_label"))
        seen[k] = seen.get(k, 0) + 1
        if seen[k] == 2:
            repeats.append(k[1])
    results.append(result(FEATURE, "no target is pointed at twice", "fail" if repeats else "pass", "live-machine",
                          f"repeated targets: {repeats}; stop reason {stop['reason']}" if repeats else "every target pointed at once"))

    # 4 detours (Refresh, registration link, navigation) are not part of the path
    detours = [(r["index"], r.get("target_label")) for r in points
               if r.get("target_role") == "AXLink" or DETOUR.search(r.get("target_label") or "")]
    results.append(result(FEATURE, "no detour controls (Refresh, 'here', navigation) are pointed at",
                          "fail" if detours else "pass", "live-machine",
                          f"pointed at detours: {detours}" if detours else "no detours"))

    # 5 orientation once; no repeated first sentence
    bad = [r["index"] for r in decisions[1:] if ORIENTATION.search(r.get("instruction_en", ""))]
    firsts = {}
    for r in decisions:
        firsts.setdefault(_follow.first_sentence(r.get("instruction_en", "")), []).append(r["index"])
    shared = {s: i for s, i in firsts.items() if s and len(i) > 1}
    results.append(result(FEATURE, "orientation text appears only in the first decision",
                          "fail" if bad or shared else "pass", "live-machine",
                          f"orientation wording in decisions {bad}; first sentence shared by decisions {shared}" if bad or shared
                          else "no repeated orientation wording"))

    # 6 filled control never pointed at
    filled = [(r["index"], r["target_label"]) for r in points if r.get("filled_before") is True]
    results.append(result(FEATURE, "a filled control is never pointed at", "fail" if filled else "pass", "live-machine",
                          f"pointed at already-filled controls: {filled}" if filled else "every pointed control was empty when pointed at"))

    # 7 validated
    invalid = [r["index"] for r in points if r.get("valid") is not True]
    results.append(result(FEATURE, "every pointer validated", "fail" if invalid or not decisions else "pass", "live-machine",
                          f"unvalidated decisions {invalid}" if invalid else
                          f"{len(decisions)} decisions, sources {sorted({r.get('source') for r in decisions})}, {len(reader_errors)} reader pauses"))

    # 8 completion
    last = decisions[-1] if decisions else None
    receipt_ok, receipt_detail = False, "no receipt file"
    if RECEIPT.exists():
        try:
            body = json.loads(RECEIPT.read_text())
            fresh = RECEIPT.stat().st_mtime >= started
            receipt_ok = fresh and set(body) == {"task", "synthetic", "completed_at"} and body.get("task") == "kseb_practice"
            receipt_detail = f"receipt keys {sorted(body)}, fresh={fresh}"
        except ValueError as exc:
            receipt_detail = f"receipt unreadable: {exc}"
    done = bool(last and last["kind"] == "complete") and heading_seen and receipt_ok
    results.append(result(FEATURE, "completion: practice bill shown + fresh receipt, ended by a complete decision",
                          "pass" if done else "fail", "live-machine",
                          f"last decision {last['kind'] if last else None}; '{STATUS_TEXT}' on page={heading_seen}; "
                          f"{receipt_detail}; driver stop={stop['reason']}; {where}"))
    results.append(result(FEATURE, "person follows the pointer on the KSEB copy, reads the image", "skip", "needs-human",
                          "driver typed the practice image text; a person has not read a captcha or run this (see features/web-support.md)"))
    return results
