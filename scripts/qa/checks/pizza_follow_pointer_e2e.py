"""Follow-the-pointer e2e on a real-shaped form: the local pizza page (same structure as httpbin's form).

LIVE + SARVAM: the planner is the Sarvam planner (`--task web_any` default), so every tick costs chat
calls (about 10-15 per run). BLOCKED unless QA_LIVE_SARVAM=1 and a SARVAM_API_KEY is available.
It also brings a Safari window to the front, so run it when nobody is using Safari.

One question ("Can you help me fill this form?"), no further input. The test-only driver
(scripts/drive_follow_pointer.py) acts only on the control the companion points at, then waits for the
next decision. Reproduces the integration bugs found by hand: misordered steps, skipped Pizza Size set,
orientation text repeated at every step.

Policy (Abin's retest): optional units are offered, not skipped. Expected walk: name, phone, email, Pizza Size
(set), Pizza Toppings (optional, driver presses Skip), Preferred delivery time (optional, driver presses Skip:
Safari's time input cannot be driven), Delivery instructions (optional, driver types a sample), Submit, complete.
Each optional unit is offered once and says "optional"; after the first step the wording is "Next...", never
"Start with". The driver presses the companion panel's Skip button (`companion-skip`, our own app).
"""
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from _common import PY, ROOT, result, wait_for
import _follow
import _web

FEATURE = "web-support"
QUESTION = "Can you help me fill this form?"
REQUIRED_ORDER = ["Customer name:", "Telephone:", "E-mail address:", "Pizza Size", "Submit order"]
# The real page marks nothing required; the companion offers these three, in reading order, as "(optional)".
OPTIONAL_UNITS = ["Pizza Toppings", "Preferred delivery time:", "Delivery instructions:"]
OPTIONAL_SET = "Pizza Toppings"
START_WITH = re.compile(r"\bstart with\b", re.IGNORECASE)
NEXT_WORD = re.compile(r"\bnext\b", re.IGNORECASE)
SIZE_OPTIONS = {"Small", "Medium", "Large"}
TOPPINGS = {"Bacon", "Extra Cheese", "Onion", "Mushroom"}
RECEIPT = ROOT / "runs" / "pizza-complete.json"
STATUS_TEXT = "Order received (practice)"
ORIENTATION = re.compile(r"\b(?:this is an? [\w\- ]{0,30}form|order form|this (?:page|form|website|site) (?:is|lets|allows))\b",
                         re.IGNORECASE)


def run():
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, "pizza follow-the-pointer (Sarvam planner)", "blocked", "blocked",
                       "set QA_LIVE_SARVAM=1: live Sarvam planner, ~10-15 chat calls per run, and it puts a Safari window in front")]
    if not _follow.key_available():
        return [result(FEATURE, "pizza follow-the-pointer (Sarvam planner)", "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]

    err = _web.ensure_pizza_route() or _web.open_pizza_front()
    if err:
        return [result(FEATURE, "pizza page ready in front Safari window", "blocked", "live-machine", err)]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_file = ROOT / "runs" / f"pizza-follow-{stamp}.jsonl"
    before = set((ROOT / "runs").glob("session-*.jsonl"))
    started = time.time()
    app = subprocess.Popen([PY, "-m", "companion.app", "--task", "web_any", "--mute", "--question", QUESTION],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        log = wait_for(lambda: next(iter(set((ROOT / "runs").glob("session-*.jsonl")) - before), None), 10)
        if log is None:
            return [result(FEATURE, "companion start", "fail", "live-machine",
                           app.stderr.read()[-500:] if app.poll() is not None else "no session log within 10 s")]
        d = subprocess.run([PY, "scripts/drive_follow_pointer.py", "--companion-pid", str(app.pid),
                            "--log", str(log), "--out", str(out_file),
                            "--decision-timeout", "40", "--total-timeout", "240"],
                           cwd=ROOT, capture_output=True, text=True, timeout=300)
        time.sleep(1.0)
        heading_seen = _heading_seen()
    finally:
        app.send_signal(signal.SIGTERM)
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()
        _web.close_and_settle(_web.PIZZA_URL)

    records = [json.loads(l) for l in out_file.read_text().splitlines()] if out_file.exists() else []
    return assess(records, d.returncode, d.stderr, heading_seen, started, out_file, log)


def assess(records, driver_rc, driver_err, heading_seen, started, out_file, log):
    """Turn the driver's records into results. Pure apart from reading the receipt file."""
    decisions = [r for r in records if r["event"] == "decision"]
    stop = next((r for r in records if r["event"] == "stop"), {"reason": f"driver produced no summary (rc={driver_rc}): {driver_err[-200:]}"})
    reader_errors = [r for r in records if r["event"] == "reader_error"]
    points = [r for r in decisions if r["kind"] == "point"]
    labels = [r.get("target_label") for r in points]
    full_list = "\n".join(_follow.line(r) for r in decisions)
    print(f"\n--- pizza follow-the-pointer: {len(decisions)} decisions, stop={stop['reason']} ---\n{full_list}\n--- end ---")
    where = f"decision list: {out_file}; session log: {log}"

    # 1 order
    positions, missing = [], []
    # an option of a set counts as the set
    normal = ["Pizza Size" if l in SIZE_OPTIONS else OPTIONAL_SET if l in TOPPINGS else l for l in labels]
    for want in REQUIRED_ORDER:
        idx = next((i for i, l in enumerate(normal) if l == want), None)
        (missing if idx is None else positions).append(want if idx is None else idx)
    in_order = not missing and positions == sorted(positions)
    extras = [l for l in normal if l not in REQUIRED_ORDER]
    order_detail = (f"order {labels}; missing {missing}; required positions {positions} "
                    f"(want strictly increasing); extras {extras}; {where}")
    results = [result(FEATURE, "required steps pointed in order: name, phone, email, Pizza Size, Submit",
                      "pass" if in_order else "fail", "live-machine",
                      f"{order_detail}\nDECISIONS:\n{full_list}" if not in_order else order_detail)]

    # 2 pizza size covered
    size_hit = "Pizza Size" in normal
    results.append(result(FEATURE, "Pizza Size set is pointed at", "pass" if size_hit else "fail", "live-machine",
                          "pointed at the Pizza Size set" if size_hit else f"never pointed at Pizza Size; targets were {labels}"))

    # 3 no repeats
    seen, repeats = {}, []
    for r in points:
        k = (r.get("target_role"), r.get("target_label"))
        seen[k] = seen.get(k, 0) + 1
        if seen[k] == 2:
            repeats.append(k[1])
    results.append(result(FEATURE, "no target is pointed at twice", "fail" if repeats else "pass", "live-machine",
                          f"repeated targets: {repeats}; stop reason {stop['reason']}" if repeats else "every target pointed at once"))

    # 4 orientation text only in the first decision
    bad = [r["index"] for r in decisions[1:] if ORIENTATION.search(r.get("instruction_en", ""))]
    firsts = {}
    for r in _follow.walk_decisions(decisions):
        firsts.setdefault(_follow.first_sentence(r.get("instruction_en", "")), []).append(r["index"])
    shared = {s: i for s, i in firsts.items() if s and len(i) > 1}
    results.append(result(FEATURE, "orientation text appears only in the first decision",
                          "fail" if bad or shared else "pass", "live-machine",
                          f"orientation wording in decisions {bad}; first sentence shared by decisions {shared}" if bad or shared
                          else "no repeated orientation wording"))

    # 5 never point at a filled control
    filled = [(r["index"], r["target_label"]) for r in points if r.get("filled_before") is True]
    results.append(result(FEATURE, "a filled control is never pointed at", "fail" if filled else "pass", "live-machine",
                          f"pointed at already-filled controls: {filled}" if filled else "every pointed control was empty when pointed at"))

    # 6 optional units: offered in reading order, each once, saying "optional"
    optional_pos = {u: [i for i, l in enumerate(normal) if l == u] for u in OPTIONAL_UNITS}
    offered_once = {u: len(v) == 1 for u, v in optional_pos.items()}
    says_optional = {u: bool(v) and all(re.search(r"optional", points[i].get("instruction_en", ""), re.IGNORECASE) for i in v)
                     for u, v in optional_pos.items()}
    firsts_pos = [v[0] for v in optional_pos.values() if v]
    size_pos = next((i for i, l in enumerate(normal) if l == "Pizza Size"), None)
    submit_pos = next((i for i, l in enumerate(normal) if l == "Submit order"), None)
    between = all(size_pos is not None and submit_pos is not None and size_pos < p < submit_pos for p in firsts_pos)
    ordered = len(firsts_pos) == len(OPTIONAL_UNITS) and firsts_pos == sorted(firsts_pos) and between
    skips = [r["target_label"] for r in points if r.get("action") == "pressed Skip"]
    results.append(result(FEATURE, "optional units offered in reading order: Pizza Toppings, delivery time, delivery instructions",
                          "pass" if ordered else "fail", "live-machine",
                          f"positions {optional_pos}; between Pizza Size ({size_pos}) and Submit ({submit_pos}): {between}; "
                          f"Skip pressed on {skips}"))
    bad_once = [u for u in OPTIONAL_UNITS if not offered_once[u]]
    bad_word = [u for u in OPTIONAL_UNITS if not says_optional[u]]
    results.append(result(FEATURE, "each optional unit is offered exactly once and says \"optional\"",
                          "fail" if bad_once or bad_word else "pass", "live-machine",
                          f"not offered exactly once: { {u: len(optional_pos[u]) for u in bad_once} }; "
                          f"missing the word 'optional': {bad_word}" if bad_once or bad_word
                          else "Pizza Toppings, Preferred delivery time and Delivery instructions each offered once, each marked optional"))

    # 6b wording after the first step: "Next...", never "Start with"
    starts = [r["index"] for r in decisions[1:] if START_WITH.search(r.get("instruction_en", ""))]
    no_next = [r["index"] for r in decisions[1:] if r["kind"] == "point" and r.get("target_role") != "AXButton"
               and not NEXT_WORD.search(r.get("instruction_en", ""))]
    results.append(result(FEATURE, "no \"Start with\" after the first step",
                          "fail" if starts else "pass", "live-machine",
                          f"'Start with' in decisions {starts}" if starts else "only the first decision opens with 'Start with'"))
    results.append(result(FEATURE, "later field steps are phrased \"Next...\"",
                          "fail" if no_next else "pass", "live-machine",
                          f"decisions without 'Next' (fields only, buttons exempt): {no_next}" if no_next
                          else "every later field step says Next"))

    # 7 every pointer validated, no reader pauses
    invalid = [r["index"] for r in decisions if r["kind"] == "point" and r.get("valid") is not True]
    results.append(result(FEATURE, "every pointer validated", "fail" if invalid or not decisions else "pass", "live-machine",
                          f"unvalidated decisions {invalid}" if invalid else
                          f"{len(decisions)} decisions, sources {sorted({r.get('source') for r in decisions})}, "
                          f"{len(reader_errors)} reader pauses"))

    # 8 completion
    last = decisions[-1] if decisions else None
    receipt_ok, receipt_detail = False, "no receipt file"
    if RECEIPT.exists():
        try:
            body = json.loads(RECEIPT.read_text())
            fresh = RECEIPT.stat().st_mtime >= started
            receipt_ok = fresh and set(body) == {"task", "synthetic", "completed_at"} and body.get("task") == "pizza_practice"
            receipt_detail = f"receipt keys {sorted(body)}, fresh={fresh}"
        except ValueError as exc:
            receipt_detail = f"receipt unreadable: {exc}"
    done = bool(last and last["kind"] == "complete") and heading_seen and receipt_ok
    results.append(result(FEATURE, "completion: status text + fresh receipt, ended by a complete decision",
                          "pass" if done else "fail", "live-machine",
                          f"last decision {last['kind'] if last else None}; '{STATUS_TEXT}' on page={heading_seen}; "
                          f"{receipt_detail}; driver stop={stop['reason']}; {where}"))
    results.append(_follow.scroll_result(FEATURE, decisions))
    results.append(result(FEATURE, "person follows the pointer on a real-shaped form", "skip", "needs-human",
                          "driver acted on the pointed control; a person has not run this (see features/web-support.md)"))
    return results


def _heading_seen() -> bool:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("drive_follow_pointer", ROOT / "scripts" / "drive_follow_pointer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        area = mod.pizza_area()
        queue = [area]
        while queue:
            el = queue.pop()
            if mod._get(el, "AXRole") == "AXHeading" and STATUS_TEXT in str(mod._get(el, "AXTitle") or ""):
                return True
            queue.extend(mod._get(el, "AXChildren") or [])
    except (SystemExit, Exception):  # noqa: BLE001 - page gone or unreadable counts as not seen
        return False
    return False
