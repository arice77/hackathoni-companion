"""GitHub-only simulation and opt-in Devin session adapters."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .case import REPO, ROOT, Case
from .replay import CaseError, command, detached, git, resolve

FIX_SHA = "93c6dea50660695a11e3ee54018262bd829ba376"
FIX_PATHS = {"companion/sites/youtube.py", "companion/planner_sarvam.py", "tests/test_site_youtube.py"}
SIM_TITLE = "[SIMULATED Devin] Recognise 'make it faster' locally"
SIM_BODY = "SIMULATED: the patch is our builder's fix from 93c6dea, run through the same flow Devin would use."
PR_URL = re.compile(rf"https://github\.com/{re.escape(REPO)}/pull/([1-9][0-9]*)")
GH_HELPER = ("-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential")


@dataclass(frozen=True)
class Session:
    id: str
    pr_url: str | None = None
    api_version: str | None = None


@dataclass(frozen=True)
class PullRequest:
    url: str
    head_sha: str


def _check_origin(repo: Path) -> None:
    expected = f"https://github.com/{REPO}.git"
    if any(git("remote", "get-url", *option, "origin", cwd=repo) != expected
           for option in ((), ("--push",))):
        raise CaseError(f"origin's fetch and push URLs must be {expected}.")


def _remote_ref(repo: Path, branch: str) -> str | None:
    ref = "refs/heads/" + branch
    line = git(*GH_HELPER, "ls-remote", "--heads", "origin", ref, cwd=repo)
    return line.split()[0] if line else None


def _push_new(repo: Path, branch: str, revision: str) -> None:
    ref = "refs/heads/" + branch
    # The empty lease ensures an existing branch can never be moved by this command.
    git(*GH_HELPER, "push", f"--force-with-lease={ref}:", "origin", f"{revision}:{ref}", cwd=repo)


def _ensure_base(repo: Path, case: Case, sha: str) -> None:
    _check_origin(repo)
    published = _remote_ref(repo, case.branch)
    if published is None:
        _push_new(repo, case.branch, sha)
    elif published != sha:
        raise CaseError("The GitHub case branch has moved from the approved baseline.")


def _read_pr(repo: Path, case: Case, url: str) -> PullRequest:
    if not PR_URL.fullmatch(url):
        raise CaseError("The repair PR is outside the configured GitHub repository.")
    info = json.loads(command("gh", "pr", "view", url, "--repo", REPO, "--json",
                              "url,state,baseRefName,baseRefOid,headRefOid", cwd=repo))
    sha = info.get("headRefOid", "")
    if (info.get("url") != url or info.get("state") != "OPEN" or info.get("baseRefName") != case.branch
            or info.get("baseRefOid") != resolve(case.base_sha, repo)
            or not re.fullmatch(r"[0-9a-f]{40}", sha)):
        raise CaseError("GitHub did not report an open PR with the approved base and an exact head SHA.")
    _check_origin(repo)
    git(*GH_HELPER, "fetch", "--no-tags", "--no-write-fetch-head", "origin", sha, cwd=repo)
    return PullRequest(url, sha)


class SimulatedDevin:
    mode = "simulated"

    def __init__(self, repo: Path = ROOT):
        self.repo = repo

    def start_fix(self, case: Case, *, evidence: dict) -> Session:
        if case.id != "make-it-faster":
            raise CaseError("No simulated patch is registered for this case.")
        base = evidence["revision"]
        branch = case.branch + "-fix"
        _check_origin(self.repo)
        if _remote_ref(self.repo, branch):
            raise CaseError("This case already has a GitHub fix branch.")
        with detached(base, self.repo) as worktree:
            git("cherry-pick", "--no-commit", FIX_SHA, cwd=worktree)
            changed = set(git("diff", "--cached", "--name-only", cwd=worktree).splitlines())
            if changed != FIX_PATHS:
                raise CaseError("The pinned fix did not match the expected implementation and test files.")
            git("-c", "user.name=arice77", "-c", "user.email=arice77@users.noreply.github.com",
                "commit", "-m", "Recognise YouTube speed commands locally", cwd=worktree)
            head = resolve("HEAD", worktree)
            _ensure_base(self.repo, case, base)
            _push_new(worktree, branch, head)
        url = command("gh", "pr", "create", "--repo", REPO, "--base", case.branch, "--head", branch,
                      "--title", SIM_TITLE, "--body-file", "-", cwd=self.repo, input=SIM_BODY + "\n")
        if not PR_URL.fullmatch(url):
            raise CaseError("GitHub did not return the simulated pull request URL.")
        return Session(f"simulated-{head}", url)

    def wait_for_pr(self, case: Case, session: Session) -> PullRequest:
        return _read_pr(self.repo, case, session.pr_url or "")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _devin_config(repo: Path) -> tuple[str, str]:
    names = {"DEVIN_API_KEY", "DEVIN_ORG_ID"}
    config = {}
    path = repo / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and name.strip() in names:
                config[name.strip()] = value.strip().strip("\"'")
    config.update({name: os.environ[name].strip() for name in names if name in os.environ})
    key, org = config.get("DEVIN_API_KEY", ""), config.get("DEVIN_ORG_ID", "")
    if not key.startswith(("cog_", "apk_")):
        raise CaseError("Live mode needs a supported DEVIN_API_KEY in the environment or .env.")
    if key.startswith("cog_") and not re.fullmatch(r"[A-Za-z0-9_-]+", org):
        raise CaseError("A Devin v3 key needs DEVIN_ORG_ID in the environment or .env.")
    return key, org


def _prompt(case: Case, evidence: dict) -> str:
    repro = f".venv/bin/python -m tools.devin_case.replay {case.id} <revision>"
    return (
        f"Repair case {case.id} in {REPO}. Work from {case.branch} at {evidence['revision']}.\n"
        f"Use a new fix branch and open a PR into {case.branch}. Leave it open for manual review.\n"
        "Keep the change and regression tests limited to this case.\n"
        f"Repro from a checkout with the case tool and Git revisions: {repro}\n"
        f"Question: {case.question}\n"
        f"Expected: {json.dumps(case.expected)}\nActual: {json.dumps(evidence['actual'])}\n"
        f"Evidence: {json.dumps(evidence)}\nSynthetic snapshot: {json.dumps(case.snapshot)}\n"
    )


class LiveDevin:
    mode = "live"
    poll_seconds = 15
    timeout_seconds = 30 * 60
    max_acu = 5

    def __init__(self, repo: Path = ROOT):
        self.repo = repo
        self._key, org = _devin_config(repo)
        self.api_version = "v3" if self._key.startswith("cog_") else "v1"
        path = f"/v3/organizations/{org}/sessions" if self.api_version == "v3" else "/v1/sessions"
        self._endpoint = f"https://api.devin.ai{path}"
        self._opener = build_opener(_NoRedirect())

    def _request(self, method: str, suffix: str = "", payload: dict | None = None) -> dict:
        request = Request(self._endpoint + suffix, method=method,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=20) as response:
                body = json.load(response)
        except HTTPError as exc:
            raise CaseError(f"Devin API {method} returned HTTP {exc.code}.") from None
        except (URLError, OSError, ValueError):
            raise CaseError(f"Devin API {method} did not return a readable response.") from None
        if not isinstance(body, dict):
            raise CaseError("Devin API returned an unexpected response.")
        return body

    def start_fix(self, case: Case, *, evidence: dict) -> Session:
        _ensure_base(self.repo, case, evidence["revision"])
        payload = {
            "prompt": _prompt(case, evidence),
            "title": f"Fix case {case.id}",
            "max_acu_limit": self.max_acu,
            "tags": ["hackathoni-qa", case.id],
        }
        if self.api_version == "v1":
            payload["idempotent"] = True
        else:
            payload["repos"] = [REPO]
        response = self._request("POST", payload=payload)
        session_id = response.get("session_id", "")
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
            raise CaseError("Devin did not return a usable session ID.")
        return Session(session_id, api_version=self.api_version)

    def wait_for_pr(self, case: Case, session: Session) -> PullRequest:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", session.id):
            raise CaseError("Invalid Devin session ID in local state.")
        if session.api_version != self.api_version:
            raise CaseError("The saved session uses a different Devin API version.")
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            info = self._request("GET", f"/{session.id}")
            status = " ".join(str(info.get(key) or "").casefold().replace("_", " ")
                              for key in ("status", "status_enum", "status_detail"))
            for reason in ("out of credits", "suspended", "expired", "error", "blocked"):
                if re.search(rf"\b{reason}\b", status):
                    raise CaseError(f"Devin stopped ({reason}). The session ID is saved for review.")
            if self.api_version == "v1":
                url = (info.get("pull_request") or {}).get("url")
            else:
                url = next((pr.get("pr_url") for pr in info.get("pull_requests") or []
                            if (pr.get("pr_state") or "").casefold() == "open"), None)
            if url:
                return _read_pr(self.repo, case, url)
            if info.get("status") == "exit" or info.get("status_enum") == "finished":
                raise CaseError("Devin finished without an open PR. The session ID is saved for review.")
            time.sleep(min(self.poll_seconds, max(0, deadline - time.monotonic())))
        raise CaseError("Timed out waiting for Devin's PR. The session ID is saved for resuming.")
