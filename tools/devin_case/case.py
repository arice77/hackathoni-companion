"""Checked-in inputs for deterministic Devin repair cases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent
REPO = "arice77/hackathoni-companion"


@dataclass(frozen=True)
class Case:
    id: str
    base_sha: str
    question: str
    snapshot: dict
    expected: dict
    baseline: dict

    @property
    def branch(self) -> str:
        return f"devin-case/{self.id}"

    @property
    def approval(self) -> str:
        return f"fix {self.id} {self.base_sha[:7]}"

    def confirms_failure(self, evidence: dict) -> bool:
        return (evidence["revision"].startswith(self.base_sha)
                and evidence["passed"] is False
                and evidence["expected"] == self.expected
                and evidence["actual"] == self.baseline["actual"]
                and evidence["intent_calls"] == self.baseline["intent_calls"])


def load_case(case_id: str) -> Case:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id):
        raise ValueError("Invalid case ID.")
    path = DIRECTORY / "cases" / f"{case_id.replace('-', '_')}.json"
    case = Case(**json.loads(path.read_text()))
    if case.id != case_id or not re.fullmatch(r"[0-9a-f]{7,40}", case.base_sha):
        raise ValueError("Case ID or baseline revision does not match the fixture.")
    return case
