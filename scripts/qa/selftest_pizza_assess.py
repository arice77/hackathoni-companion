"""Offline self-test of the follow-the-pointer checks' assertions (pizza and KSEB): a good run must pass, a buggy run
must fail each rule it breaks. No screen, no Safari, no Sarvam.

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


def dec(i, label, text, filled=False, role="AXTextField", times=1, kind="point", action="x"):
    rec = {"event": "decision", "index": i, "kind": kind, "valid": True, "instruction_en": text, "source": "sarvam", "action": action}
    if kind == "point":
        rec.update(target_label=label, target_role=role, filled_before=filled, times_pointed=times)
    return rec


GOOD = [
    dec(0, "Customer name:", "This is an order form. Start with 'Customer name:'."),
    dec(1, "Telephone:", "Next, enter the phone number in 'Telephone:'."),
    dec(2, "E-mail address:", "Next, enter your e-mail in 'E-mail address:'."),
    dec(3, "Pizza Size", "Next, choose a size in 'Pizza Size'.", role="AXGroup"),
    dec(4, "Pizza Toppings", "Next, 'Pizza Toppings' (optional): tick any you like, or skip.", role="AXGroup", action="pressed Skip"),
    dec(5, "Preferred delivery time:", "Next, 'Preferred delivery time:' (optional).", role="AXDateTimeArea", action="pressed Skip"),
    dec(6, "Delivery instructions:", "Next, 'Delivery instructions:' (optional): add a note if you want.", role="AXTextArea"),
    dec(7, "Submit order", "Next, click 'Submit order'.", role="AXButton"),
    dec(8, None, "Done, your order is in.", kind="complete"),
    {"event": "stop", "reason": "complete"},
]
BAD = [  # what Abin saw: wrong order, Pizza Size skipped, orientation repeated, a filled field re-pointed
    dec(0, "Telephone:", "This is an order form. Enter the phone in 'Telephone:'."),
    dec(1, "Customer name:", "This is an order form. Start with 'Customer name:'."),
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
for needle in ("required steps", "Pizza Size", "no target", "orientation", "a filled control", "completion",
               "optional units offered", "each optional unit", "Start with"):
    assert any(needle in k for k in fails), (needle, fails)

# ---- KSEB ----
spec = importlib.util.spec_from_file_location("kseb", ROOT / "scripts/qa/checks/kseb_follow_pointer_e2e.py")
kseb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kseb)

KGOOD = [
    dec(0, "13 digit Consumer number", "This is the Quick Pay page. Enter your 13 digit consumer number."),
    dec(1, "Enter Mobile Number", "Enter the mobile number registered with KSEB."),
    dec(2, "Enter text shown below", "Read the text in the image and type it here; I cannot read it for you."),
    dec(3, "Submit to see the bill", "Click 'Submit to see the bill'.", role="AXButton"),
    dec(4, None, "Your practice bill is showing.", kind="complete"),
    {"event": "stop", "reason": "complete"},
]
KBAD = [  # captcha before mobile, guesses the captcha, detours via Refresh twice, orientation repeated
    dec(0, "13 digit Consumer number", "This is the Quick Pay page. Enter the number."),
    dec(1, "Enter text shown below", "This is the Quick Pay page. Type PRACTICE.", ),
    dec(2, "Refresh", "This is the Quick Pay page. Refresh the image.", role="AXLink"),
    dec(3, "Refresh", "This is the Quick Pay page. Refresh the image.", role="AXLink", times=2),
    {"event": "stop", "reason": "repeat:Refresh"},
]


def kstatuses(records, receipt):
    rc = kseb.ROOT / "runs" / "kseb-complete.json"
    backup = rc.read_bytes() if rc.exists() else None
    try:
        if receipt:
            rc.write_text(json.dumps({"task": "kseb_practice", "synthetic": True, "completed_at": "t"}))
        else:
            rc.unlink(missing_ok=True)
        got = kseb.assess(records, 0, "", receipt, time.time() - 60, Path("/tmp/x.jsonl"), Path("/tmp/log.jsonl"))
    finally:
        rc.unlink(missing_ok=True)
        if backup is not None:
            rc.write_bytes(backup)
    return {r["check"][:48]: r["status"] for r in got if r["evidence"] != "needs-human"}


kgood, kbad = kstatuses(KGOOD, True), kstatuses(KBAD, False)
print("kseb good:", kgood)
print("kseb bad: ", kbad)
assert set(kgood.values()) == {"pass"}, kgood
kfails = [k for k, v in kbad.items() if v == "fail"]
for needle in ("steps pointed in order", "captcha guidance", "no target", "no detour", "orientation", "completion"):
    assert any(needle in k for k in kfails), (needle, kfails)

# ---- optional scroll step ("Scroll down to continue." before Submit) ----
def with_scroll(records, before_label, action="scrolled page down to 0.60", times=1):
    out = []
    for r in records:
        if r.get("target_label") == before_label:
            out += [dec(0, None, "Scroll down to continue.", kind="clarify", action=action) for _ in range(times)]
        out.append(r)
    n = 0
    for r in out:
        if r["event"] == "decision":
            r["index"], n = n, n + 1
    return out


sg = statuses(with_scroll(GOOD, "Submit order"), True)
assert set(sg.values()) == {"pass"}, sg  # one answered scroll, then progress: nothing else flags it
assert any(k.startswith("scrolling is optional") for k in sg), sg
for bad_scroll in (with_scroll(GOOD, "Submit order", action="none"),  # driver did not scroll
                   with_scroll(GOOD, "Submit order", times=4),  # more than 3 scrolls
                   GOOD[:7] + [dec(7, None, "Scroll down to continue.", kind="clarify", action="scrolled page down to 0.60"),
                               {"event": "stop", "reason": "decision-timeout"}]):  # no progress after the scroll
    bs = statuses(bad_scroll, True)
    assert [v for k, v in bs.items() if k.startswith("scrolling is optional")] == ["fail"], bs
ks = kstatuses(with_scroll(KGOOD, "Submit to see the bill"), True)
assert set(ks.values()) == {"pass"}, ks
print("scroll step OK")
print("self-test OK")
