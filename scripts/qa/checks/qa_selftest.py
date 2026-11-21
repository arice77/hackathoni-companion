"""Self-test of the QA assertions themselves (no screen, Safari or Sarvam): a good decision list must pass the
pizza rules and an Abin-style buggy one must fail each rule it breaks."""
from _common import PY, result, sh

FEATURE = "qa-harness"


def run():
    p = sh(PY, "scripts/qa/selftest_pizza_assess.py", timeout=60)
    ok = p.returncode == 0 and "self-test OK" in p.stdout
    return [result(FEATURE, "pizza assertions: good run passes, buggy run fails", "pass" if ok else "fail", "automated",
                   "self-test OK" if ok else (p.stderr or p.stdout)[-500:])]
