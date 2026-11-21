"""Helpers shared by QA checks."""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = str(ROOT / ".venv" / "bin" / "python")


def result(feature, check, status, evidence, detail=""):
    """status: pass|fail|blocked|skip. evidence: automated|live-machine|needs-human."""
    return {"feature": feature, "check": check, "status": status, "evidence": evidence, "detail": str(detail)}


def sh(*args, timeout=120, **kw):
    return subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True, timeout=timeout, **kw)


def wait_for(fn, seconds=8.0, every=0.25):
    end = time.time() + seconds
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(every)
    return None


sys.path.insert(0, str(ROOT))
