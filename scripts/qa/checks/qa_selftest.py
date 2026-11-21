"""Self-test of the QA assertions themselves (no screen, Safari or Sarvam): a good decision list must pass the
pizza, KSEB, YouTube and Gmail rules and a buggy one must fail each rule it breaks."""
from _common import PY, result, sh

FEATURE = "qa-harness"


def run():
    out = []
    p = sh(PY, "scripts/qa/selftest_pizza_assess.py", timeout=60)
    ok = p.returncode == 0 and "self-test OK" in p.stdout
    out.append(result(FEATURE, "follow-pointer assertions (pizza + KSEB): good run passes, buggy run fails", "pass" if ok else "fail", "automated",
                      "self-test OK" if ok else (p.stderr or p.stdout)[-500:]))
    p = sh(PY, "scripts/qa/selftest_site_assess.py", timeout=60)
    ok = p.returncode == 0 and "site self-test OK" in p.stdout
    out.append(result(FEATURE, "follow-pointer assertions (YouTube + Gmail, Gmail privacy scan, driver allowlist): good walk passes, bad walk fails each rule",
                      "pass" if ok else "fail", "automated", "site self-test OK" if ok else (p.stderr or p.stdout)[-500:]))
    return out
