"""Shared shapes between reader, planner, validator, overlay and voice.

Owned by the coordinator. Agents may read this file but must not change it;
propose changes in their final report instead.

Coordinates: every Rect is (x, y, width, height) in *global screen points with
a top-left origin on the primary display* -- the convention macOS Accessibility
(AXPosition/AXSize) already uses. Converting to AppKit's bottom-left origin is
the overlay's job and nobody else's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Control:
    id: str  # unique within one snapshot, e.g. "c07"
    role: str  # AXButton, AXTextField, AXPopUpButton, AXStaticText ...
    label: str  # title / description / placeholder. Never a typed field value.
    frame: Rect
    enabled: bool = True
    identifier: str | None = None  # AXIdentifier when the app provides one
    # Whether an input holds something (text typed, option chosen, box ticked).
    # The reader records only this boolean, never the content. None = not an input.
    filled: bool | None = None
    # For options inside a choice set (radio buttons, a fieldset of checkboxes): the set's label,
    # e.g. "Pizza Size". A choice set itself is reported as a Control with role "AXGroup" or
    # "AXRadioGroup", its label, and filled=True once any option in it is selected.
    group: str | None = None


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    taken_at: float  # time.time()
    app_bundle_id: str
    app_pid: int
    window_title: str
    window_frame: Rect
    controls: tuple[Control, ...] = field(default_factory=tuple)
    viewport: Rect | None = None

    def control(self, control_id: str) -> Control | None:
        return next((c for c in self.controls if c.id == control_id), None)


DecisionKind = Literal["point", "clarify", "unsupported", "complete"]
DecisionSource = Literal["scripted", "sarvam", "mock"]


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    snapshot_id: str
    instruction: str  # short; may be Malayalam with English control labels kept
    instruction_en: str = ""  # English gloss shown as subtitle
    control_id: str | None = None  # required when kind == "point"
    source: DecisionSource = "scripted"


class PointerOverlay(Protocol):
    """Click-through highlight + short callout.

    Create and call only on the main thread of a running NSApplication.
    """

    def show(self, frame: Rect, instruction: str, subtitle: str = "") -> None: ...

    def hide(self) -> None: ...


@dataclass(frozen=True)
class Transcript:
    text: str
    language_code: str  # e.g. "ml-IN"
    provider: str  # "sarvam", "utter", "typed"
    model: str = ""
    request_id: str = ""
    latency_ms: float = 0.0
