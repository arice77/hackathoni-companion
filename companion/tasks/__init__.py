"""Task scripts: one module per practice fixture. Each module defines TASK (a Task).

A Task tells the scripted planner which app to read, which questions it handles, the ordered
steps per screen, and how the fixture proves the task finished.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    identifier: str  # AXIdentifier of the control to point at
    ml: str  # Malayalam instruction (English control labels kept in quotes)
    en: str  # English gloss shown as subtitle
    done_note: str | None = None  # identifier of a status/note text that proves the step happened
    done_prefix: str = ""


@dataclass(frozen=True)
class Screen:
    title_prefix: str  # matched against the static text with identifier "screen-title"
    steps: tuple[Step, ...]
    final: Step | None  # the screen's last button, or None if the screen ends with a status message


@dataclass(frozen=True)
class Task:
    name: str
    bundle_id: str
    intent: re.Pattern
    screens: tuple[Screen, ...]
    complete_status_prefix: str  # text of the "status" identifier once finished
    complete_ml: str
    complete_en: str
    receipt_file: str  # file the fixture writes into runs/ when finished
    unsupported_ml: str = "ഈ ജോലിക്ക് മാത്രമേ ഇപ്പോൾ സഹായിക്കാൻ കഴിയൂ."
    unsupported_en: str = "Right now I can only guide this one task."
    notes: dict = field(default_factory=dict)
    page_title: str | None = None
    page_url_prefix: str | None = None


def load(name: str) -> Task:
    return importlib.import_module(f"companion.tasks.{name}").TASK
