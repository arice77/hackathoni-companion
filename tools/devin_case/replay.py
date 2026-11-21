"""Run the same synthetic player case against a detached Git revision."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from .case import ROOT, Case, load_case


class CaseError(RuntimeError):
    pass


def command(*args: str, cwd: Path = ROOT, timeout: float = 60, input: str | None = None) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, input=input, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise CaseError(f"{args[0]} could not run or timed out.") from None
    if result.returncode:
        raise CaseError(f"{' '.join(args[:2])} exited {result.returncode}: {result.stderr.strip()[-600:]}")
    return result.stdout.strip()


def git(*args: str, cwd: Path = ROOT) -> str:
    return command("git", "-c", "core.hooksPath=/dev/null", *args, cwd=cwd)


def resolve(revision: str, repo: Path = ROOT) -> str:
    return git("rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}", cwd=repo)


@contextmanager
def detached(revision: str, repo: Path = ROOT):
    with TemporaryDirectory(prefix="devin-case-") as temporary:
        worktree = Path(temporary) / "checkout"
        git("worktree", "add", "--quiet", "--detach", str(worktree), revision, cwd=repo)
        try:
            yield worktree
        finally:
            git("worktree", "remove", "--force", str(worktree), cwd=repo)


_WORKER = """
import json
import sys


def offline(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise RuntimeError("External operations are blocked in the replay")


sys.addaudithook(offline)
sys.path.insert(0, sys.argv[1])
from companion.contracts import Control, Snapshot
from companion.planner_sarvam import SarvamPlanner
from companion.sites.youtube import parse_intent
from companion.validator import validate
from companion.voice import sarvam

calls = 0


def blocked(*args, **kwargs):
    global calls
    calls += 1
    raise sarvam.SarvamError("Sarvam network blocked in offline replay")


sarvam._post = blocked
sarvam._load_api_key = lambda: "offline-replay-key"
case = json.load(sys.stdin)
expected = case["expected"]
raw = case["snapshot"]
raw["controls"] = tuple(Control(**dict(c, frame=tuple(c["frame"]))) for c in raw["controls"])
for key in ("window_frame", "viewport"):
    raw[key] = tuple(raw[key])
snap = Snapshot(**raw)
question = case["question"]
intent = parse_intent(question)
decision = SarvamPlanner("web_site", log_calls=False).decide(question, snap)
target = snap.control(decision.control_id)
valid, reason = validate(decision, snap, now=snap.taken_at)
if not valid:
    raise RuntimeError("Replay produced an invalid decision: " + reason)
actual = {
    "kind": decision.kind,
    "target_label": target.label if target else None,
    "local_intent": {"action": intent.action, "speed": str(intent.speed) if intent.speed is not None else None}
                    if intent else None,
}
print(json.dumps({
    "revision": sys.argv[2],
    "passed": {**actual, "intent_calls": calls} == expected,
    "actual": actual,
    "expected": expected,
    "intent_calls": calls,
}))
"""


def replay(case: Case, revision: str, *, repo: Path = ROOT) -> dict:
    checked_sha = resolve(revision, repo)
    with detached(checked_sha, repo) as worktree:
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "LANG", "LC_ALL") if key in os.environ}
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", _WORKER, str(worktree), checked_sha], cwd=worktree,
                input=json.dumps({"question": case.question, "snapshot": case.snapshot, "expected": case.expected}),
                env=env, text=True, capture_output=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise CaseError("Replay subprocess could not run or timed out.") from None
        if result.returncode:
            raise CaseError(f"Replay subprocess exited {result.returncode}: {result.stderr.strip()[-600:]}")
        try:
            return json.loads(result.stdout)
        except ValueError:
            raise CaseError("Replay subprocess did not produce JSON evidence.") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("revision", nargs="?")
    args = parser.parse_args()
    try:
        case = load_case(args.case_id)
        evidence = replay(case, args.revision or case.base_sha)
    except (CaseError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
