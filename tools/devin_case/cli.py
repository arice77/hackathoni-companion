"""Approve and review a one-shot repair case. The default adapter is simulated."""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .adapters import LiveDevin, Session, SimulatedDevin
from .case import DIRECTORY, ROOT, Case, load_case
from .replay import CaseError, replay


@contextmanager
def _locked_state(path: Path):
    with path.with_suffix(".json.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {}
        previous = json.dumps(state, sort_keys=True)
        yield state
        current = json.dumps(state, indent=2, sort_keys=True)
        if json.dumps(state, sort_keys=True) != previous:
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(current + "\n")
            temporary.replace(path)


def _review(case, mode, pr, before, after) -> str:
    verdict = "PASS" if after["passed"] else "FAIL"
    return (
        f"# Repair case {case.id}\n\n"
        f"Mode **{mode.upper()}**\n\n"
        f"[Open pull request for manual review]({pr.url})\n\n"
        f"Checked PR head `{pr.head_sha}`\n\n"
        f"| Replay | Revision | Result | Intent calls |\n"
        f"| --- | --- | --- | --- |\n"
        f"| Before | `{before['revision']}` | FAIL | {before['intent_calls']} |\n"
        f"| After | `{after['revision']}` | {verdict} | {after['intent_calls']} |\n\n"
        "The replay blocks Sarvam requests. Intent calls count attempts, including the blocked baseline attempt.\n\n"
        "**Replay evidence**\n\n"
        "```json\n"
        + json.dumps({"before": before, "after": after}, indent=2)
        + "\n```\n"
    )


def run_case(
    case: Case,
    adapter,
    *,
    state_path: Path = DIRECTORY / "state.json",
    report_dir: Path = ROOT / "docs/devin-cases",
    ask=input,
    run_replay=replay,
    show=print,
) -> int:
    before = run_replay(case, case.base_sha)
    show(json.dumps({"baseline": before}, indent=2))
    if not case.confirms_failure(before):
        raise CaseError("The approved baseline did not reproduce the expected assertion failure.")
    with _locked_state(state_path) as state:
        record = state.get(case.id, {}).get(adapter.mode)
    if record is None:
        show(f"Review the {adapter.mode.upper()} repair for {case.id} at {before['revision']}.")
        try:
            accepted = ask(f"Type `{case.approval}` to start the repair: ")
        except EOFError:
            accepted = ""
        if accepted != case.approval:
            raise CaseError("Approval did not match the case and baseline.")
        with _locked_state(state_path) as state:
            attempts = state.setdefault(case.id, {})
            if adapter.mode in attempts:
                raise CaseError("Another invocation reserved this case. Rerun to resume its saved session.")
            attempts[adapter.mode] = {"base": before["revision"], "session": None}
        # Reserve before side effects. A lost response must not permit a duplicate job.
        session = adapter.start_fix(case, evidence=before)
        with _locked_state(state_path) as state:
            state[case.id][adapter.mode]["session"] = asdict(session)
    else:
        if record["base"] != before["revision"]:
            raise CaseError("The case already belongs to another baseline in local state.")
        if record["session"] is None:
            raise CaseError("A start was reserved but no session ID was saved. Reconcile the remote outcome before retrying.")
        session = Session(**record["session"])
        show(f"Resuming recorded {adapter.mode} session {session.id}.")
    pr = adapter.wait_for_pr(case, session)
    show(f"Review PR {pr.url} at {pr.head_sha}")
    after = run_replay(case, pr.head_sha)
    if after["revision"] != pr.head_sha:
        raise CaseError("The replay did not check the exact PR head.")
    report = _review(case, adapter.mode, pr, before, after)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{case.id}-{adapter.mode}-{date.today().isoformat()}.md"
    with _locked_state(state_path):
        path.write_text(report)
    show(report)
    show(f"Report written to {path}")
    return 0 if after["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("--live", action="store_true", help="use a real Devin session")
    args = parser.parse_args()
    try:
        case = load_case(args.case_id)
        adapter = LiveDevin() if args.live else SimulatedDevin()
        return run_case(case, adapter)
    except KeyboardInterrupt:
        print("Interrupted. A reserved attempt remains in local state.", file=sys.stderr)
        return 130
    except (CaseError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
