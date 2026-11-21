"""Do the offline replays catch regressions? Inject a fault into the product module (in memory only) and require the
matching scenario to FAIL. No screen, Safari or Sarvam.

    .venv/bin/python scripts/qa/selftest_replay_mutations.py
"""
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "qa" / "checks"):
    sys.path.insert(0, str(p))

import gmail_replay as gm  # noqa: E402
import youtube_replay as yt  # noqa: E402
from companion.sites import gmail as gmail_pack, youtube as yt_pack  # noqa: E402


ORIG_CHOICE = yt_pack.ResultChoice


def passes(module, name):
    r = next(x for x in module.run() if x["check"].endswith(name))
    return r["status"] == "pass"


# the unmutated replays are green
assert all(r["status"] == "pass" for r in yt.run() + gm.run()), [r["check"] for r in yt.run() + gm.run() if r["status"] != "pass"]

MUTATIONS = [
    # (module, scenario name, description, patch target, replacement)
    (yt, "arrow stays on the title anchor", "title anchors not recognised (bug 5)", (yt_pack, "_is_title_anchor"), lambda c: False),
    (yt, "player ad waits then skips then completes", "ad markers never seen near the player (bug 7 inverse)",
     (yt_pack, "_player_ad_controls"), lambda controls: ()),
    (yt, "hover preview ads on results are ignored", "results pages treated as non-results, ads count (bug 7)",
     (yt_pack, "_looks_like_results"), lambda controls, links: False),
    (yt, "scrolled past the choice says scroll back", "the chosen result's score is forgotten, so weaker matches win (bug 6)",
     (yt_pack, "ResultChoice"), lambda key, title, score, anchor: ORIG_CHOICE(key, title, (False, 0, False, 0, 0, -10**6), anchor)),
    (yt, "faster points at the 1 25 preset and completes", "speed presets ignored", (yt_pack, "_SPEED_PRESET"),
     __import__("re").compile(r"(?!)")),
    (gm, "private question text never reaches a decision", "question privacy filter removed",
     (gmail_pack.PACK.privacy, "filter_question"), lambda question: question),
]
for module, name, why, (target, attr), repl in MUTATIONS:
    assert passes(module, name), f"{name}: not green before mutation"
    with mock.patch.object(target, attr, repl):
        caught = not passes(module, name)
    assert caught, f"MISSED regression: {why} did not fail {name!r}"
    print(f"caught: {why}")
print("replay mutation self-test OK")
