"""Next-step planners.

`ScriptedPlanner` walks a task script (companion/tasks/<name>.py): on the recognised screen it
points at the first unfinished step, judged from the *live* snapshot. It understands questions
only through the task's keyword regex, and is labelled "scripted" in the UI and logs so it is
never mistaken for an AI planner. A Sarvam planner can sit behind the same `decide()`.
"""

from __future__ import annotations

from typing import Protocol

from .contracts import Control, Decision, Snapshot
from .tasks import Step, Task, load


class Planner(Protocol):
    name: str

    def decide(self, question: str, snap: Snapshot) -> Decision: ...


def _by_ident(snap: Snapshot, ident: str) -> Control | None:
    return next((c for c in snap.controls if c.identifier == ident), None)


def _step_done(snap: Snapshot, step: Step) -> bool | None:
    if _by_ident(snap, step.identifier) is None:
        return None
    if step.done_note:
        note = _by_ident(snap, step.done_note)
        return None if note is None else note.label.startswith(step.done_prefix)
    return bool(_by_ident(snap, step.identifier).filled)


class ScriptedPlanner:
    name = "scripted"

    def __init__(self, task: Task | str = "aims"):
        self.task = load(task) if isinstance(task, str) else task

    def decide(self, question: str, snap: Snapshot) -> Decision:
        t, sid = self.task, snap.snapshot_id
        q = question.strip()
        if not q:
            return Decision("clarify", sid, "എന്താണ് ചെയ്യേണ്ടത് എന്ന് പറയൂ.",
                            "Say or type what you want to do.", source="scripted")
        if not t.intent.search(q):
            return Decision("unsupported", sid, t.unsupported_ml, t.unsupported_en, source="scripted")

        status = _by_ident(snap, "status")
        if status and status.label.startswith(t.complete_status_prefix):
            return Decision("complete", sid, t.complete_ml, t.complete_en, source="scripted")

        title = _by_ident(snap, "screen-title")
        screen = next((s for s in t.screens if title and title.label.startswith(s.title_prefix)), None)
        if screen is None:
            return Decision("unsupported", sid, "ഈ സ്ക്രീൻ തിരിച്ചറിയാൻ കഴിഞ്ഞില്ല.",
                            "I don't recognise this screen.", source="scripted")

        for step in screen.steps:
            done = _step_done(snap, step)
            if done is None:
                return Decision("unsupported", sid, "പ്രതീക്ഷിച്ച ബോക്സ് ഈ സ്ക്രീനിൽ കാണുന്നില്ല.",
                                f"Expected control ‘{step.identifier}’ is missing.", source="scripted")
            if not done:
                return Decision("point", sid, step.ml, step.en, _by_ident(snap, step.identifier).id, "scripted")
        if screen.final is None:
            return Decision("unsupported", sid, "ഈ സ്ക്രീനിൽ അടുത്ത പടി കാണുന്നില്ല.",
                            "No next step found on this screen.", source="scripted")
        target = _by_ident(snap, screen.final.identifier)
        if target is None:
            return Decision("unsupported", sid, "അടുത്ത ബട്ടൺ കാണുന്നില്ല.", "The next button is missing.",
                            source="scripted")
        return Decision("point", sid, screen.final.ml, screen.final.en, target.id, "scripted")
