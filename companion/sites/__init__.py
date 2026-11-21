"""Host-scoped guidance and provider privacy profiles."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

from ..contracts import Control, Decision, Snapshot


def _phrase(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split()).rstrip(" ?!.,।")


@dataclass(frozen=True)
class SiteStep:
    role: str
    label: str
    ml: str
    en: str
    action: bool = False

    def matches(self, control: Control) -> bool:
        return self.role == control.role and _phrase(self.label) == _phrase(control.label)

    def target(self, snap: Snapshot) -> Control | None:
        matches = [c for c in snap.controls if c.enabled and self.matches(c)]
        return matches[0] if len(matches) == 1 else None

    def point(self, snap: Snapshot, control: Control) -> Decision:
        return Decision("point", snap.snapshot_id, self.ml, self.en, control.id, "sarvam")


@dataclass(frozen=True)
class SiteGoal:
    name: str
    phrases: tuple[str, ...]
    step: SiteStep | None = None


@dataclass(frozen=True)
class PrivacyProfile:
    allowed_controls: frozenset[tuple[str, str]]
    private_question: re.Pattern | None = None

    def permits(self, control: Control) -> bool:
        return (control.role, _phrase(control.label)) in self.allowed_controls

    def filter_snapshot(self, snap: Snapshot) -> Snapshot:
        return replace(snap, controls=tuple(c for c in snap.controls if self.permits(c)))

    def filter_question(self, question: str) -> str:
        return self.private_question.sub("[redacted]", question) if self.private_question else question


@dataclass(frozen=True)
class SitePack:
    name: str
    hosts: frozenset[str]
    practice_heading: str
    goals: tuple[SiteGoal, ...]
    entry: SiteStep
    steps: tuple[SiteStep, ...]
    privacy: PrivacyProfile
    practice_result: str

    def goal_for(self, question: str) -> SiteGoal | None:
        utterances = {_phrase(part) for part in question.split(" / ", 1)}
        return next((goal for goal in self.goals if any(_phrase(p) in utterances for p in goal.phrases)), None)

    def is_practice(self, snap: Snapshot) -> bool:
        return snap.window_title in {"127.0.0.1", "localhost"} and (
            any(c.role == "AXHeading" and _phrase(c.label) in {
                _phrase(self.practice_heading), _phrase(self.practice_result),
            } for c in snap.controls)
            or self.steps[-1].target(snap) is not None
        )

    def matches(self, snap: Snapshot) -> bool:
        host = snap.window_title.casefold().rstrip(".")
        return host in self.hosts or self.is_practice(snap)


def pack_for(snap: Snapshot) -> SitePack | None:
    from .kseb import PACK

    return PACK if PACK.matches(snap) else None
