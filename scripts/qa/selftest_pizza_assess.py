"""Offline self-test of the pizza check's assertions: a good run must pass, an Abin-style buggy run must fail
each rule it breaks. No screen, no Safari, no Sarvam.

    .venv/bin/python scripts/qa/selftest_pizza_assess.py
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "qa" / "checks"))
spec = importlib.util.spec_from_file_location("pizza", ROOT / "scripts/qa/checks/pizza_follow_pointer_e2e.py")
pizza = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pizza)


def dec(i, label, text, filled=False, role="AXTextField", times=1, kind="point"):
    rec = {"event": "decision", "index": i, "kind": kind, "valid": True, "instruction_en": text, "source": "sarvam", "action": "x"}
    if kind == "point":
        rec.update(target_label=label, target_role=role, filled_before=filled, times_pointed=times)
    return rec


GOOD = [
    dec(0, "Customer name:", "This is an order form. Enter your name in 'Customer name:'."),
    dec(1, "Telephone:", "Enter the phone number in 'Telephone:'."),
    dec(2, "E-mail address:", "Enter your e-mail in 'E-mail address:'."),
    dec(3, "Pizza Size", "Choose a size in 'Pizza Size'.", role="AXGroup"),
    dec(4, "Submit order", "Click 'Submit order'.", role="AXButton"),
    dec(5, None, "Done, your order is in.", kind="complete"),
    {"event": "stop", "reason": "complete"},
]
BAD = [  # what Abin saw: wrong order, Pizza Size skipped, orientation repeated, a filled field re-pointed
    dec(0, "Telephone:", "This is an order form. Enter the phone in 'Telephone:'."),
    dec(1, "Customer name:", "This is an order form. Enter your name.", ),
    dec(2, "Customer name:", "This is an order form. Enter your name.", filled=True, times=2),
    dec(3, "E-mail address:", "This is an order form. Enter e-mail."),
    dec(4, "Submit order", "This is an order form. Click Submit.", role="AXButton"),
    {"event": "stop", "reason": "repeat:Customer name:"},
]


def statuses(records, receipt):
    rc = pizza.ROOT / "runs" / "pizza-complete.json"
    backup = rc.read_bytes() if rc.exists() else None
    try:
        if receipt:
            rc.write_text(json.dumps({"task": "pizza_practice", "synthetic": True, "completed_at": "t"}))
        else:
            rc.unlink(missing_ok=True)
        got = pizza.assess(records, 0, "", receipt, time.time() - 60, Path("/tmp/x.jsonl"), Path("/tmp/log.jsonl"))
    finally:
        rc.unlink(missing_ok=True)
        if backup is not None:
            rc.write_bytes(backup)
    return {r["check"].split(":")[0][:40]: r["status"] for r in got if r["evidence"] != "needs-human"}


good, bad = statuses(GOOD, True), statuses(BAD, False)
print("good:", good)
print("bad: ", bad)
assert set(good.values()) == {"pass"}, good
assert [v for v in bad.values()].count("pass") <= 2 and "fail" in bad.values(), bad
fails = [k for k, v in bad.items() if v == "fail"]
for needle in ("required steps", "Pizza Size", "no target", "orientation", "a filled control", "completion"):
    assert any(needle in k for k in fails), (needle, fails)
print("self-test OK")
