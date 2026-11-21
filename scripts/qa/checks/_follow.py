"""Helpers shared by the follow-the-pointer checks (pizza, KSEB)."""
import importlib.util
import os
import re

from _common import ROOT


def key_available() -> bool:
    """A SARVAM_API_KEY exists in the environment or .env (the value is never read into a result)."""
    if os.environ.get("SARVAM_API_KEY"):
        return True
    env = ROOT / ".env"
    return env.exists() and any(line.strip().startswith("SARVAM_API_KEY=") and line.strip() != "SARVAM_API_KEY="
                                for line in env.read_text().splitlines())


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0].strip().lower()


def line(rec: dict) -> str:
    who = rec.get("target_label") or rec["kind"]
    return (f"#{rec['index']} {rec['kind']} {who!r} filled_before={rec.get('filled_before')} "
            f"x{rec.get('times_pointed', '-')} -> {rec.get('action')} | \"{rec.get('instruction_en', '')}\"")


def load_follow_driver(page: str):
    spec = importlib.util.spec_from_file_location("drive_follow_pointer", ROOT / "scripts" / "drive_follow_pointer.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.configure(page)
    return mod


def heading_seen(page: str, text: str) -> bool:
    """Is there an AXHeading containing `text` on our page right now? (test-side read)"""
    try:
        mod = load_follow_driver(page)
        queue = [mod.pizza_area(wait=2.0)]
        while queue:
            el = queue.pop()
            if mod._get(el, "AXRole") == "AXHeading" and text in str(mod._get(el, "AXTitle") or ""):
                return True
            queue.extend(mod._get(el, "AXChildren") or [])
    except (SystemExit, Exception):  # noqa: BLE001 - page gone or unreadable counts as not seen
        return False
    return False
