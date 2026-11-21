"""Offline replay helpers: synthetic Accessibility states through the real SarvamPlanner, network blocked.

No Safari, no screen, no Sarvam. Controls use the labels and identifiers observed live (see features/web-support.md):
YouTube `youtube-watch:<video-hash>:<anchor-hash>` (title anchors start with `a`, thumbnails with `b`), the player's
paused label "Play keyboard shortcut k", the speed panel's "Decrease playback speed 0.05" and "Playback speed slider <n>".
Any attempt to reach the network fails the scenario unless it installs a fake provider on purpose (labelled mock).
"""
import json
import time
import urllib.request
from contextlib import contextmanager
from unittest import mock

from _common import ROOT  # noqa: F401  (puts the repo on sys.path)
from companion.contracts import Control, Snapshot
from companion.planner_sarvam import SarvamPlanner
from companion.validator import validate
from companion.voice import sarvam

WIN = (0, 0, 1200, 900)


def C(cid, role, label, frame=None, *, filled=None, identifier=None, enabled=True):
    return Control(cid, role, label, frame or (100, 100, 120, 30), enabled, identifier, filled)


def snap(controls, *, host="www.youtube.com", below=0, tick=0):
    return Snapshot(f"s{tick}", time.time(), "com.apple.Safari", 4242, host, WIN, tuple(controls), viewport=WIN,
                    below_fold_count=below)


@contextmanager
def blocked_network(provider=None):
    """No network. `provider(payload) -> response dict` installs a fake Sarvam chat reply (a mock, labelled as such)."""
    calls = []

    def boom(*a, **k):
        raise AssertionError("scenario tried to reach the network")

    def fake_post(endpoint, key, body, content_type):
        calls.append(json.loads(body))
        if provider is None:
            boom()
        return provider(calls[-1]), 1.0

    with mock.patch.object(urllib.request, "urlopen", boom), \
            mock.patch.object(sarvam, "_load_api_key", (lambda: "test-key") if provider else boom), \
            mock.patch.object(sarvam, "_post", fake_post):
        yield calls


def planner():
    return SarvamPlanner("web_site", log_calls=False)


class Walk:
    """One question asked of one planner across successive screens. `step` checks one decision."""

    def __init__(self, question, pl=None):
        self.question, self.pl, self.tick = question, pl or planner(), 0
        self.log = []

    def step(self, screen, kind, label=None, text=None, *, role=None, not_text=None):
        self.tick += 1
        s = Snapshot(f"{screen.snapshot_id}-{self.tick}", screen.taken_at, screen.app_bundle_id, screen.app_pid,
                     screen.window_title, screen.window_frame, screen.controls, screen.viewport, screen.below_fold_count)
        d = self.pl.decide(self.question, s)
        got = s.control(d.control_id).label if d.control_id else None
        self.log.append(f"{d.kind}:{got or ''}:{d.instruction_en[:50]}")
        assert d.kind == kind, f"step {self.tick}: want {kind}, got {d.kind} ({d.instruction_en[:70]!r}); so far {self.log}"
        if kind == "point":
            ok, why = validate(d, s)
            assert ok, f"step {self.tick}: pointer failed validation: {why}"
            if label is not None:
                assert got is not None and label.lower() in got.lower(), f"step {self.tick}: want target {label!r}, got {got!r}"
            if role is not None:
                assert s.control(d.control_id).role == role, f"step {self.tick}: want role {role}, got {s.control(d.control_id).role}"
        if text is not None:
            assert text.lower() in d.instruction_en.lower(), f"step {self.tick}: want {text!r} in {d.instruction_en!r}"
        if not_text is not None:
            assert not_text.lower() not in d.instruction_en.lower(), f"step {self.tick}: {not_text!r} must not appear in {d.instruction_en!r}"
        return d
