import io
import json
import os
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from tools.devin_case import adapters
from tools.devin_case.case import load_case
from tools.devin_case.cli import run_case
from tools.devin_case.replay import CaseError, detached


BASE = "329cc68aceb40097e6f45e131e7fb5224b15977f"
HEAD = "a" * 40
PR = adapters.PullRequest("https://github.com/arice77/hackathoni-companion/pull/123", HEAD)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.case = load_case("make-it-faster")
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.state = self.root / "state.json"
        self.before = {"revision": BASE, "passed": False, "expected": self.case.expected, **self.case.baseline}
        self.after = {"revision": HEAD, "passed": True, "expected": self.case.expected, "intent_calls": 0,
                      "actual": {key: value for key, value in self.case.expected.items() if key != "intent_calls"}}
        self.adapter = Mock(mode="simulated")
        self.adapter.start_fix.return_value = adapters.Session("simulated-test", PR.url)
        self.adapter.wait_for_pr.return_value = PR
        self.ask = Mock(return_value=self.case.approval)
        self.show = Mock()

    def run_flow(self, *results):
        return run_case(self.case, self.adapter, state_path=self.state, report_dir=self.root, ask=self.ask,
                        show=self.show, run_replay=Mock(side_effect=results))

    def test_confirmed_case_saves_session_before_waiting_and_reuses_it(self):
        def wait(case, session):
            record = json.loads(self.state.read_text())[self.case.id]["simulated"]
            self.assertEqual(record["session"]["id"], session.id)
            return PR

        self.adapter.wait_for_pr.side_effect = wait
        self.assertEqual(self.run_flow(self.before, self.after), 0)
        self.assertEqual(self.run_flow(self.before, self.after), 0)
        self.ask.assert_called_once()
        self.adapter.start_fix.assert_called_once_with(self.case, evidence=self.before)
        self.assertEqual(self.adapter.wait_for_pr.call_count, 2)
        report = next(self.root.glob("*.md")).read_text()
        for value in ("SIMULATED", PR.url, HEAD, "FAIL", "PASS"):
            self.assertIn(value, report)

    def test_wrong_revision_or_unexpected_failure_cannot_be_approved(self):
        for unexpected in ({"revision": HEAD}, {"actual": {}}, {"intent_calls": 0}, {"passed": True}):
            with self.subTest(unexpected=unexpected), self.assertRaisesRegex(CaseError, "assertion failure"):
                self.run_flow({**self.before, **unexpected})
        self.ask.assert_not_called()
        self.adapter.start_fix.assert_not_called()

    def test_typed_approval_is_bound_to_the_case_and_base(self):
        self.ask.return_value = "fix make-it-faster 93c6dea"
        with self.assertRaisesRegex(CaseError, "Approval"):
            self.run_flow(self.before)
        self.adapter.start_fix.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_uncertain_start_does_not_send_a_second_request(self):
        self.adapter.start_fix.side_effect = CaseError("lost response")
        with self.assertRaisesRegex(CaseError, "lost response"):
            self.run_flow(self.before)
        with self.assertRaisesRegex(CaseError, "reserved"):
            self.run_flow(self.before)
        self.adapter.start_fix.assert_called_once()

    def test_simulation_does_not_consume_the_single_live_session(self):
        self.assertEqual(self.run_flow(self.before, self.after), 0)
        live = Mock(mode="live")
        live.start_fix.return_value = adapters.Session("devin-live-test", api_version="v1")
        live.wait_for_pr.return_value = PR
        for _ in range(2):
            self.assertEqual(run_case(self.case, live, state_path=self.state, report_dir=self.root,
                                      ask=self.ask, show=self.show, run_replay=Mock(side_effect=(self.before, self.after))), 0)
        self.assertEqual(self.ask.call_count, 2)
        live.start_fix.assert_called_once()
        attempts = json.loads(self.state.read_text())[self.case.id]
        self.assertEqual(set(attempts), {"simulated", "live"})
        report = next(self.root.glob("*.md")).read_text()
        self.assertEqual(report.count("Mode **SIMULATED**"), 1)
        self.assertEqual(report.count("Mode **LIVE**"), 1)

    def test_rejects_after_evidence_at_a_different_head(self):
        with self.assertRaisesRegex(CaseError, "exact PR head"):
            self.run_flow(self.before, {**self.after, "revision": BASE})
        self.assertEqual(list(self.root.glob("*.md")), [])


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.case = load_case("make-it-faster")
        self.evidence = {"revision": BASE, **self.case.baseline}
        self.repo = Path(self.enterContext(TemporaryDirectory()))

    def test_simulated_adapter_pins_patch_and_opens_review_into_case_branch(self):
        def fake_git(*args, cwd):
            return "\n".join(sorted(adapters.FIX_PATHS)) if args[:2] == ("diff", "--cached") else ""

        with (patch.object(adapters, "git", side_effect=fake_git) as git,
              patch.object(adapters, "detached", return_value=nullcontext(self.repo)),
              patch.object(adapters, "_check_origin"), patch.object(adapters, "_remote_ref", return_value=None),
              patch.object(adapters, "_ensure_base") as base, patch.object(adapters, "_push_new") as push,
              patch.object(adapters, "resolve", return_value=HEAD),
              patch.object(adapters, "command", return_value=PR.url) as gh):
            session = adapters.SimulatedDevin(self.repo).start_fix(self.case, evidence=self.evidence)
        base.assert_called_once_with(self.repo, self.case, BASE)
        push.assert_called_once_with(self.repo, self.case.branch + "-fix", HEAD)
        git.assert_any_call("cherry-pick", "--no-commit", adapters.FIX_SHA, cwd=self.repo)
        self.assertIn(self.case.branch, gh.call_args.args)
        self.assertEqual(gh.call_args.kwargs["input"], adapters.SIM_BODY + "\n")
        self.assertEqual(session.pr_url, PR.url)

    def test_live_modes_use_documented_routes_and_limits(self):
        for key, org, version in (("apk_user_unit", "", "v1"), ("cog_unit", "org-test", "v3")):
            with self.subTest(version=version), patch.dict(os.environ, {
                "DEVIN_API_KEY": key, "DEVIN_ORG_ID": org,
            }, clear=True):
                adapter = adapters.LiveDevin(self.repo)
                pr_data = ({"pull_request": {"url": PR.url}} if version == "v1" else
                           {"pull_requests": [{"pr_url": PR.url, "pr_state": "open"}]})
                with (patch.object(adapters, "_ensure_base"), patch.object(adapter._opener, "open") as request,
                      patch.object(adapters, "_read_pr", return_value=PR)):
                    request.side_effect = [io.BytesIO(json.dumps(data).encode()) for data in (
                        {"session_id": "devin-demo"}, {"status": "running", **pr_data})]
                    session = adapter.start_fix(self.case, evidence=self.evidence)
                    self.assertEqual(adapter.wait_for_pr(self.case, session), PR)
                post, get = (call.args[0] for call in request.call_args_list)
                self.assertEqual(post.get_header("Authorization"), f"Bearer {key}")
                path = "/v1/sessions" if version == "v1" else f"/v3/organizations/{org}/sessions"
                self.assertEqual(post.full_url, "https://api.devin.ai" + path)
                self.assertEqual(get.full_url, post.full_url + "/devin-demo")
                payload = json.loads(post.data)
                self.assertEqual(payload["max_acu_limit"], 5)
                self.assertIn(self.case.branch, payload["prompt"])
                if version == "v1":
                    self.assertIs(payload["idempotent"], True)
                else:
                    self.assertEqual(payload["repos"], ["arice77/hackathoni-companion"])

    def test_terminal_live_states_stop_without_a_second_request(self):
        with patch.dict(os.environ, {"DEVIN_API_KEY": "cog_unit", "DEVIN_ORG_ID": "org-test"}, clear=True):
            adapter = adapters.LiveDevin(self.repo)
        for status in ({"status": "error"}, {"status": "suspended"}, {"status_detail": "out_of_credits"}):
            with self.subTest(status=status), patch.object(adapter, "_request", return_value=status) as request:
                with self.assertRaisesRegex(CaseError, "Devin stopped"):
                    adapter.wait_for_pr(self.case, adapters.Session("devin-demo", api_version="v3"))
                request.assert_called_once()

    def test_detached_checkout_is_removed_even_when_the_replay_raises(self):
        with patch("tools.devin_case.replay.git") as git:
            with self.assertRaisesRegex(ValueError, "test error"):
                with detached(BASE, self.repo) as worktree:
                    raise ValueError("test error")
        git.assert_any_call("worktree", "add", "--quiet", "--detach", str(worktree), BASE, cwd=self.repo)
        git.assert_called_with("worktree", "remove", "--force", str(worktree), cwd=self.repo)
