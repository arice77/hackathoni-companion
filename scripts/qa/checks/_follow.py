"""Helpers shared by the follow-the-pointer checks (pizza, KSEB)."""
import importlib.util
import os
import re

from _common import ROOT, result


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


MAX_SCROLLS = 3


def is_scroll(rec: dict) -> bool:
    """A 'Scroll down to continue.' clarify (the planner asks the person to bring the next control into view)."""
    low = rec.get("instruction_en", "").lower()
    return rec.get("event") == "decision" and rec.get("kind") == "clarify" and "scroll" in low and "scroll inside" not in low


def walk_decisions(decisions):
    """Decisions that count for wording rules: scroll clarifies are a legitimate extra step and are not compared."""
    return [r for r in decisions if not is_scroll(r)]


def scroll_result(feature: str, decisions):
    """Optional scroll step: allowed up to MAX_SCROLLS times; each must have been answered by the driver scrolling our
    page and be followed by a point or complete decision (the walk went on)."""
    scrolls = [i for i, r in enumerate(decisions) if is_scroll(r)]
    name = "scrolling is optional and, when asked for, progresses the walk"
    if not scrolls:
        return result(feature, name, "pass", "live-machine", "no scroll needed in this window size")
    unanswered = [decisions[i]["index"] for i in scrolls if not str(decisions[i].get("action", "")).startswith("scrolled")]
    stalled = [decisions[i]["index"] for i in scrolls
               if not any(r["kind"] in {"point", "complete"} for r in decisions[i + 1:])]
    ok = not unanswered and not stalled and len(scrolls) <= MAX_SCROLLS
    return result(feature, name, "pass" if ok else "fail", "live-machine",
                  f"{len(scrolls)} scroll step(s); driver did not scroll for decisions {unanswered}; "
                  f"no progress after decisions {stalled}; limit {MAX_SCROLLS}")
