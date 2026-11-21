"""Ordered form units and progress derived from sanitized Accessibility snapshots."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from hashlib import sha256

from .contracts import Control, Decision, Snapshot

ENTRY_ROLES = {
    "AXTextField", "AXTextArea", "AXSearchField", "AXComboBox", "AXPopUpButton",
    "AXDateField", "AXTimeField", "AXDateTimeArea",
}
GROUP_ROLES = {"AXGroup", "AXRadioGroup"}
OPTION_ROLES = {"AXRadioButton", "AXCheckBox"}
PRIMARY_ACTIONS = {"next", "continue", "save"}
WEB_PRIMARY_ACTIONS = PRIMARY_ACTIONS | {"save draft", "search", "submit order"}
_REQUIRED_LABEL = re.compile(r"(?:\*|\(required\))\s*:?$", re.IGNORECASE)
_OPTIONAL_ENTRY = re.compile(
    r"\(optional\)|\(not required\)|^preferred\b|^(?:(?:delivery|additional) )?(?:notes|comments|instructions)\s*:?$",
    re.IGNORECASE,
)
_FORM_ACTION = re.compile(r"^(?:submit|save|send|place order|confirm|finish|done|next|continue)\b", re.IGNORECASE)
_SUCCESS_STATUS = re.compile(
    r"^(?:(?:your )?(?:order|application|request|form|submission|changes|draft|message) "
    r"(?:(?:was|were|has been|have been) )?(?:received|confirmed|submitted|saved|sent|placed|complete(?:d)?|successful)"
    r"|save successful|successfully (?:submitted|saved|sent)|(?:submitted|saved|sent) successfully"
    r"|thank you for (?:your (?:order|submission)|submitting(?: your (?:application|request|form))?)"
    r"|(?:ഓർഡർ|അപേക്ഷ) (?:ലഭിച്ചു|സമർപ്പിച്ചു)|വിജയകരമായി (?:സേവ് ചെയ്തു|സമർപ്പിച്ചു))"
    r"(?: successfully)?(?:\s*\(practice\))?[.!]?$",
    re.IGNORECASE,
)
_POSSIBLE_STATUS = re.compile(r"^(?:success|thank you|(?:order |submission )?confirmation)[.!]?$", re.IGNORECASE)
ControlKey = tuple[str, str, str | None]


def label_key(label: str) -> str:
    return " ".join(label.casefold().split()).strip(" \"'“”‘’:?!.*…")


def control_key(control: Control) -> ControlKey:
    # Native AXGroup and a bounding box synthesized from its radios denote the same unit.
    role = "AXGroup" if control.role in GROUP_ROLES else control.role
    return role, label_key(control.label), label_key(control.group) if control.group else None


def reading_rank(control: Control) -> tuple[float, float]:
    return control.frame[1], control.frame[0]


def choice_option(control: Control) -> bool:
    return control.role == "AXRadioButton" or (control.role == "AXCheckBox" and bool(control.group))


def required_entry(control: Control) -> bool:
    return control.role in ENTRY_ROLES and (
        bool(_REQUIRED_LABEL.search(control.label)) or not _OPTIONAL_ENTRY.search(control.label)
    )


def _grouped_options(controls: tuple[Control, ...]) -> dict[str, list[Control]]:
    grouped = defaultdict(list)
    for c in controls:
        if c.group and c.label and c.role in OPTION_ROLES:
            grouped[c.group].append(c)
    return grouped


def with_choice_group_bounds(snap: Snapshot) -> Snapshot:
    """Supply a virtual outline target when the browser exposes only a set's options."""
    existing = {c.label for c in snap.controls if c.role in GROUP_ROLES}
    ids = {c.id for c in snap.controls}
    extra = []
    for label, options in _grouped_options(snap.controls).items():
        if label in existing:
            continue
        frames = [c.frame for c in options if c.frame[2] > 0 and c.frame[3] > 0]
        if not frames:
            continue
        left, top = min(f[0] for f in frames), min(f[1] for f in frames)
        right, bottom = max(x + w for x, _, w, _ in frames), max(y + h for _, y, _, h in frames)
        control_id = f"choice-set:{sha256(label.encode()).hexdigest()[:12]}"
        while control_id in ids:
            control_id += "_"
        ids.add(control_id)
        extra.append(Control(
            control_id, "AXGroup", label, (left, top, right - left, bottom - top),
            enabled=any(c.enabled for c in options), filled=any(c.filled is True for c in options),
        ))
    return replace(snap, controls=(*snap.controls, *extra)) if extra else snap


@dataclass(frozen=True)
class FormUnit:
    control: Control
    options: tuple[Control, ...] = ()
    optional: bool = False
    action: bool = False

    @property
    def key(self) -> ControlKey:
        return control_key(self.control)

    @property
    def filled(self) -> bool | None:
        if self.options:
            return self.control.filled is True or any(c.filled is True for c in self.options)
        return self.control.filled

    @property
    def enabled(self) -> bool:
        return any(c.enabled for c in self.options) if self.options else self.control.enabled


@dataclass(frozen=True)
class FormPlan:
    snap: Snapshot
    ordered: tuple[Control, ...]
    units: tuple[FormUnit, ...]
    groups: dict[str, FormUnit]
    heading: str

    @classmethod
    def from_snapshot(cls, snap: Snapshot) -> FormPlan:
        snap = with_choice_group_bounds(snap)
        ordered = tuple(sorted(snap.controls, key=reading_rank))
        options = _grouped_options(ordered)
        counts = Counter(c.label for c in ordered if c.role in GROUP_ROLES)
        groups = {}
        for c in ordered:
            if c.role in GROUP_ROLES and counts[c.label] == 1 and c.label in options:
                members = tuple(options[c.label])
                optional = not _REQUIRED_LABEL.search(c.label) and all(o.role == "AXCheckBox" for o in members)
                groups[c.id] = FormUnit(c, members, optional=optional)
        units = [
            groups[c.id] if c.id in groups else FormUnit(c, optional=not required_entry(c))
            for c in ordered if c.id in groups or (c.role in ENTRY_ROLES and c.label)
        ]
        primary = [
            c for c in ordered if c.enabled and c.role == "AXButton"
            and label_key(c.label).rstrip(" »›") in WEB_PRIMARY_ACTIONS
        ]
        if len(primary) == 1:
            units.append(FormUnit(primary[0], action=True))
        heading = next((
            c.label for c in ordered if c.label and (c.role == "AXHeading" or c.identifier == "screen-title")
        ), "")
        return cls(snap, ordered, tuple(units), groups, heading)

    def serialize(self, changed: set[ControlKey]) -> str:
        """Reading order, nested choices, and state flags without editable values."""
        nested = {option.id for group in self.groups.values() for option in group.options}

        def line(control: Control) -> str:
            mark = "* " if control_key(control) in changed else ""
            label = json.dumps(control.label, ensure_ascii=False)
            if control.role == "AXHeading" or control.identifier == "screen-title":
                return f"{mark}## {label}"
            state = "filled" if control.filled is True else "empty" if control.filled is False else "state unknown"
            enabled = "enabled" if control.enabled else "disabled"
            group = f" group={json.dumps(control.group, ensure_ascii=False)}" if control.group else ""
            return f"{mark}[{control.id}] {control.role} {label} ({state}, {enabled}){group}"

        lines = []
        for c in self.ordered:
            if c.id in nested:
                continue
            group = self.groups.get(c.id)
            if group is None:
                lines.append(line(c))
                continue
            kind = "optional" if group.optional else "choose one"
            state = "chosen" if group.filled else "unchosen"
            lines.append(f"{line(c)} ({kind}, {state}):")
            for option in group.options:
                mark = "x" if option.filled else " "
                lines.append(f"  ({mark}) {line(option)}")
        return "\n".join(lines)


@dataclass
class GuidanceSession:
    intro_done: bool = False
    done_keys: set[ControlKey] = field(default_factory=set)
    skipped_keys: set[ControlKey] = field(default_factory=set)
    last_key: ControlKey | None = None
    page: tuple[str, int, str, str] | None = None
    action_status: frozenset[str] | None = None

    def observe(self, plan: FormPlan) -> None:
        snap = plan.snap
        identity = snap.app_bundle_id, snap.app_pid, snap.window_title
        heading = plan.heading or (self.page[3] if self.page and self.page[:3] == identity else "")
        page = (*identity, heading)
        if page != self.page:
            self.page = page
            self.intro_done = False
            self.done_keys.clear()
            self.skipped_keys.clear()
            self.last_key = None
            self.action_status = None
        for unit in plan.units:
            if unit.filled is True:
                self.done_keys.add(unit.key)
            elif unit.filled is False:
                self.done_keys.discard(unit.key)

    def next_unit(self, plan: FormPlan) -> FormUnit | None:
        return next((
            unit for unit in plan.units
            if unit.key not in self.done_keys and not unit.optional and unit.enabled
            and (unit.action or unit.filled is False)
        ), None)

    def remember_pointer(self, target: Control, snap: Snapshot) -> None:
        key = control_key(target)
        if key == self.last_key:
            return
        self.last_key = key
        self.action_status = (
            _visible_status(snap) if target.role == "AXButton" and _FORM_ACTION.match(target.label) else None
        )

    def confirmation(self, snap: Snapshot) -> Decision | None:
        if self.action_status is None or self.page is None or snap.viewport is None:
            return None
        if (snap.app_bundle_id, snap.app_pid) != self.page[:2]:
            return None
        new_status = _visible_status(snap) - self.action_status
        if any(_SUCCESS_STATUS.fullmatch(text) for text in new_status):
            return Decision(
                "complete", snap.snapshot_id, "നന്നായി! ഈ പേജ് നടപടി പൂർത്തിയായതായി സ്ഥിരീകരിക്കുന്നു.",
                "Well done! The page confirms this step is complete.", source="sarvam",
            )
        if any(_POSSIBLE_STATUS.fullmatch(text) for text in new_status):
            return Decision(
                "clarify", snap.snapshot_id, "പൂർത്തിയായതായി തോന്നുന്നു. വീണ്ടും ശ്രമിക്കും മുമ്പ് സ്ഥിരീകരണം പരിശോധിക്കൂ.",
                "Looks like it went through. Check the confirmation before trying again.", source="sarvam",
            )
        return None


def _visible_status(snap: Snapshot) -> frozenset[str]:
    return frozenset(
        " ".join(c.label.split()) for c in snap.controls
        if c.label and c.role in {"AXHeading", "AXStaticText", "AXStatus"}
    )
