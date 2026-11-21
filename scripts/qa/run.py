"""QA runner for the HackaThoni Companion. Discovers every scripts/qa/checks/*.py.

    .venv/bin/python scripts/qa/run.py            # all checks
    .venv/bin/python scripts/qa/run.py reader e2e  # only checks whose file name contains a word

Each check module defines FEATURE (matches a file in .claude/skills/companion-qa/features/)
and run() -> list of results made with result(). Writes runs/qa/<timestamp>/report.md and
results.json. Exit code 1 if any check fails.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "checks"))
CHECKS = Path(__file__).resolve().parent / "checks"
ICON = {"pass": "PASS", "fail": "FAIL", "blocked": "BLOCKED", "skip": "SKIP"}


def main(words: list[str]) -> int:
    out = ROOT / "runs" / "qa" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(CHECKS.glob("*.py")):
        if path.name.startswith("_") or (words and not any(w in path.stem for w in words)):
            continue
        spec = importlib.util.spec_from_file_location(f"qa_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        t0 = time.time()
        try:
            spec.loader.exec_module(mod)
            got = mod.run()
        except Exception:  # a crashing check is a failing check
            got = [{"feature": getattr(mod, "FEATURE", path.stem), "check": path.stem, "status": "fail",
                    "evidence": "automated", "detail": traceback.format_exc(limit=3)}]
        for r in got:
            r.setdefault("source", path.name)
            r["seconds"] = round(time.time() - t0, 2)
            print(f"[{ICON[r['status']]:7}] {r['feature']}: {r['check']} ({r['evidence']}) {r['detail'][:160]}")
        results.extend(got)

    counts = {k: sum(r["status"] == k for r in results) for k in ICON}
    (out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    lines = [f"# QA run {out.name}", "", " · ".join(f"{v} {k}" for k, v in counts.items()), "",
             "| Status | Feature | Check | Evidence | Detail |", "|---|---|---|---|---|"]
    lines += [f"| {ICON[r['status']]} | {r['feature']} | {r['check']} | {r['evidence']} | "
              f"{r['detail'].replace('|', '/').replace(chr(10), ' ')[:300]} |" for r in results]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(f"\n{counts} -> {out / 'report.md'}")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
