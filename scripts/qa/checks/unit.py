"""All unittest suites under tests/."""
import re

from _common import PY, result, sh

FEATURE = "unit-tests"


def run():
    p = sh(PY, "-m", "unittest", "discover", "-s", "tests", "-t", ".")
    ran = re.search(r"Ran (\d+) test", p.stderr)
    n = ran.group(1) if ran else "?"
    ok = p.returncode == 0
    tail = p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ""
    return [result(FEATURE, f"unittest discover ({n} tests)", "pass" if ok else "fail", "automated",
                   tail if ok else p.stderr[-800:])]
